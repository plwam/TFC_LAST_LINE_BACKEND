"""API machine HMAC (01_BACKEND.md §9, §12) : signature, fraîcheur, idempotence, scoping.

Ces tests reconstruisent les chaînes canoniques documentées et vérifient que TOUTE divergence
(clé, signature, horodatage) est refusée en 401 — la surface machine est la plus exposée du
système (Zero Trust).
"""

import time

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import Event
from apps.sessions.models import ExamSession

pytestmark = pytest.mark.django_db

CREATE_URL = "/api/v1/machine/sessions/"
EVENTS_URL = "/api/v1/machine/events/"


def _close_url(session):
    return f"/api/v1/machine/sessions/{session.id}/close/"


def test_session_create_ok_and_canonical(project, machine_headers, now_epoch):
    issued_at = now_epoch
    message = f"{project.id}|EXAM-1|STU-1|{issued_at}"
    response = APIClient().post(
        CREATE_URL,
        {"exam_id": "EXAM-1", "student_id": "STU-1", "issued_at": issued_at},
        format="json",
        **machine_headers(message),
    )
    assert response.status_code == 201
    assert response.data["status"] == ExamSession.Status.ACTIVE
    assert ExamSession.objects.filter(project=project, exam_id="EXAM-1").exists()


def test_session_create_is_idempotent(project, machine_headers, now_epoch):
    api = APIClient()
    body = {"exam_id": "E", "student_id": "S", "issued_at": now_epoch}
    message = f"{project.id}|E|S|{now_epoch}"
    first = api.post(CREATE_URL, body, format="json", **machine_headers(message))
    # Rejouer la même requête (même date, donc même signature) doit réutiliser la session.
    second = api.post(CREATE_URL, body, format="json", **machine_headers(message))
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.data["session_id"] == second.data["session_id"]
    assert ExamSession.objects.filter(project=project, exam_id="E").count() == 1


def test_bad_signature_is_401(project, machine_headers, now_epoch):
    message = f"{project.id}|EXAM-1|STU-1|{now_epoch}"
    response = APIClient().post(
        CREATE_URL,
        {"exam_id": "EXAM-1", "student_id": "STU-1", "issued_at": now_epoch},
        format="json",
        **machine_headers(message, signature="00" * 32),
    )
    assert response.status_code == 401


def test_unknown_public_key_is_401(machine_headers, now_epoch):
    response = APIClient().post(
        CREATE_URL,
        {"exam_id": "E", "student_id": "S", "issued_at": now_epoch},
        format="json",
        **machine_headers("whatever", public_key="pk_live_does_not_exist"),
    )
    assert response.status_code == 401


def test_stale_timestamp_is_401(project, machine_headers):
    stale = int(time.time()) - 1000
    message = f"{project.id}|E|S|{stale}"
    response = APIClient().post(
        CREATE_URL,
        {"exam_id": "E", "student_id": "S", "issued_at": stale},
        format="json",
        **machine_headers(message),
    )
    assert response.status_code == 401


def test_missing_issued_at_is_401(project, machine_headers):
    response = APIClient().post(
        CREATE_URL,
        {"exam_id": "E", "student_id": "S"},
        format="json",
        **machine_headers(f"{project.id}|E|S"),
    )
    assert response.status_code == 401


def test_archived_project_keys_are_rejected(project, machine_headers, now_epoch):
    from apps.projects.services import ProjectService

    message = f"{project.id}|E|S|{now_epoch}"
    ProjectService.archive_project(project)
    response = APIClient().post(
        CREATE_URL,
        {"exam_id": "E", "student_id": "S", "issued_at": now_epoch},
        format="json",
        **machine_headers(message),
    )
    assert response.status_code == 401


def test_events_ingestion_and_duplicates(project, session, machine_headers, now_epoch):
    message = f"{project.id}|{session.id}|{now_epoch}"
    events = [
        {"event_id": "a", "type": Event.Type.FOCUS_LOST, "occurred_at": timezone.now().isoformat()},
        {"event_id": "b", "type": Event.Type.TAB_SWITCH, "occurred_at": timezone.now().isoformat()},
    ]
    api = APIClient()
    response = api.post(
        EVENTS_URL,
        {"session_id": str(session.id), "issued_at": now_epoch, "events": events},
        format="json",
        **machine_headers(message),
    )
    assert response.status_code == 202
    assert response.data == {"accepted": 2, "duplicates": 0}

    # Renvoi du MÊME lot : idempotence réseau (event_id déjà connus).
    response2 = api.post(
        EVENTS_URL,
        {"session_id": str(session.id), "issued_at": now_epoch, "events": events},
        format="json",
        **machine_headers(message),
    )
    assert response2.data == {"accepted": 0, "duplicates": 2}
    assert Event.objects.filter(session=session).count() == 2


def test_events_for_foreign_session_is_404(project, other_project, machine_headers, now_epoch):
    foreign = ExamSession.objects.create(
        project=other_project, exam_id="X", student_id="Y", started_at=timezone.now()
    )
    message = f"{project.id}|{foreign.id}|{now_epoch}"
    response = APIClient().post(
        EVENTS_URL,
        {
            "session_id": str(foreign.id),
            "issued_at": now_epoch,
            "events": [
                {"event_id": "a", "type": Event.Type.FOCUS_LOST, "occurred_at": timezone.now().isoformat()}
            ],
        },
        format="json",
        **machine_headers(message),
    )
    assert response.status_code == 404


def test_events_with_malformed_session_id_is_400(project, machine_headers, now_epoch):
    """Un identifiant non UUID est une erreur de données (400), jamais un 500 serveur."""
    message = f"{project.id}|test-session|{now_epoch}"
    response = APIClient().post(
        EVENTS_URL,
        {
            "session_id": "test-session",
            "issued_at": now_epoch,
            "events": [
                {"event_id": "a", "type": Event.Type.FOCUS_LOST, "occurred_at": timezone.now().isoformat()}
            ],
        },
        format="json",
        **machine_headers(message),
    )
    assert response.status_code == 400


def test_events_list_is_scoped_and_filtered(project, session, other_project, make_event,
                                            machine_headers, now_epoch):
    from django.utils import timezone as tz

    other_session = ExamSession.objects.create(
        project=other_project, exam_id="X", student_id="Y", started_at=tz.now()
    )
    make_event(session, event_id="a", event_type=Event.Type.FOCUS_LOST)
    make_event(session, event_id="b", event_type=Event.Type.TAB_SWITCH)
    make_event(other_session, event_id="c", event_type=Event.Type.FOCUS_LOST)

    # Lecture : les champs signés (session_id, issued_at) arrivent par les query params ; la
    # chaîne canonique reste `project_id|session_id|issued_at`.
    message = f"{project.id}|{session.id}|{now_epoch}"
    response = APIClient().get(
        EVENTS_URL,
        {
            "issued_at": now_epoch,
            "session_id": str(session.id),
            "exam_id": "EXAM-1",
            "type": Event.Type.FOCUS_LOST,
        },
        **machine_headers(message),
    )
    assert response.status_code == 200
    ids = {e["event_id"] for e in response.data}
    # Scoping projet : l'événement de l'autre projet ("c") est invisible.
    assert ids == {"a"}


def test_close_session(project, session, machine_headers, now_epoch):
    message = f"{project.id}|{session.id}|{now_epoch}"
    response = APIClient().post(
        _close_url(session),
        {"invalid": False, "issued_at": now_epoch, "session_id": str(session.id)},
        format="json",
        **machine_headers(message),
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ExamSession.Status.CLOSED
    assert session.ended_at is not None
