"""API machine HMAC (01_BACKEND.md §9, §12) : signature, fraîcheur, idempotence, scoping.

Ces tests reconstruisent les chaînes canoniques documentées et vérifient que TOUTE divergence
(clé, signature, horodatage) est refusée en 401 — la surface machine est la plus exposée du
système (Zero Trust).
"""

import time

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.hmac import derive_session_key, sign_message
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


# --- Consultation PAR EXAMEN (vue enseignant : une session = un étudiant) ------------------ #

EXAM_SESSIONS_URL = "/api/v1/machine/exam-sessions/"


def test_exam_sessions_sorted_by_risk(project, other_project, machine_headers, now_epoch):
    from apps.events.models import Event as EventModel

    low = ExamSession.objects.create(
        project=project, exam_id="EXAM-9", student_id="STU-A",
        started_at=timezone.now(), risk_score=0.118,
    )
    high = ExamSession.objects.create(
        project=project, exam_id="EXAM-9", student_id="STU-B",
        started_at=timezone.now(), risk_score=0.632,
    )
    none_score = ExamSession.objects.create(
        project=project, exam_id="EXAM-9", student_id="STU-C",
        started_at=timezone.now(), risk_score=None,
    )
    foreign = ExamSession.objects.create(
        project=other_project, exam_id="EXAM-9", student_id="STU-X",
        started_at=timezone.now(), risk_score=0.999,
    )
    EventModel.objects.create(session=high, event_id="e1", type=EventModel.Type.FOCUS_LOST,
                              occurred_at=timezone.now())

    # Canonique de consultation par examen : `project_id|exam_id|issued_at`.
    message = f"{project.id}|EXAM-9|{now_epoch}"
    response = APIClient().get(
        EXAM_SESSIONS_URL,
        {"exam_id": "EXAM-9", "issued_at": now_epoch},
        **machine_headers(message),
    )
    assert response.status_code == 200
    body = response.data
    students = [s["student_id"] for s in body["sessions"]]
    # Scoping projet : la session de l'autre projet est invisible ; tri risque décroissant,
    # score absent en fin de liste.
    assert students == ["STU-B", "STU-A", "STU-C"]
    assert body["count"] == 3
    assert body["sessions"][0]["events_count"] == 1
    assert body["sessions"][0]["risk_score"] == pytest.approx(0.632)
    assert str(high.id) == body["sessions"][0]["session_id"]
    assert none_score.risk_score is None  # gardé tel quel dans la réponse


def test_exam_sessions_sort_recent(project, machine_headers, now_epoch):
    old = ExamSession.objects.create(
        project=project, exam_id="EXAM-8", student_id="STU-OLD",
        started_at=timezone.now() - timezone.timedelta(hours=2),
    )
    new = ExamSession.objects.create(
        project=project, exam_id="EXAM-8", student_id="STU-NEW", started_at=timezone.now()
    )
    message = f"{project.id}|EXAM-8|{now_epoch}"
    response = APIClient().get(
        EXAM_SESSIONS_URL,
        {"exam_id": "EXAM-8", "issued_at": now_epoch, "sort": "recent"},
        **machine_headers(message),
    )
    assert response.status_code == 200
    assert [s["student_id"] for s in response.data["sessions"]] == ["STU-NEW", "STU-OLD"]
    assert old.status == ExamSession.Status.ACTIVE  # invariant de lecture


def test_exam_sessions_requires_exam_id(project, machine_headers, now_epoch):
    message = f"{project.id}|{now_epoch}"  # sans exam_id la canonique n'est même pas définissable
    response = APIClient().get(EXAM_SESSIONS_URL, {"issued_at": now_epoch}, **machine_headers(message))
    assert response.status_code == 401  # requête non signable avant même la validation métier


def test_exam_sessions_wrong_exam_canonical_is_401(project, machine_headers, now_epoch):
    """Signer pour un examen et lire un autre : signature invalide (401)."""
    ExamSession.objects.create(project=project, exam_id="EXAM-7", student_id="S", started_at=timezone.now())
    message = f"{project.id}|EXAM-AUTRE|{now_epoch}"
    response = APIClient().get(
        EXAM_SESSIONS_URL,
        {"exam_id": "EXAM-7", "issued_at": now_epoch},
        **machine_headers(message),
    )
    assert response.status_code == 401


# --- Clés de chambre (clé de session dérivée) --------------------------------------------- #

def test_session_create_returns_derived_session_key(project, machine_headers, now_epoch):
    """L'initiation livre la clé de chambre : HMAC-SHA256(maîtresse, "session-key|<id>")."""
    message = f"{project.id}|EXAM-K1|STU-K1|{now_epoch}"
    response = APIClient().post(
        CREATE_URL,
        {"exam_id": "EXAM-K1", "student_id": "STU-K1", "issued_at": now_epoch},
        format="json",
        **machine_headers(message),
    )
    assert response.status_code == 201
    expected = derive_session_key(str(project.secret_key), response.data["session_id"])
    assert response.data["session_key"] == expected

    # Dérivation déterministe : ré-ouvrir la MÊME session (idempotence) livre la même clé.
    second = APIClient().post(
        CREATE_URL,
        {"exam_id": "EXAM-K1", "student_id": "STU-K1", "issued_at": now_epoch},
        format="json",
        **machine_headers(message),
    )
    assert second.status_code == 200
    assert second.data["session_key"] == expected


def test_events_signed_with_room_key(project, session, machine_headers, now_epoch):
    """Signature par la clé de chambre uniquement (sans clé maîtresse) → lot accepté."""
    room_key = derive_session_key(str(project.secret_key), str(session.id))
    message = f"{project.id}|{session.id}|{now_epoch}"
    response = APIClient().post(
        EVENTS_URL,
        {
            "session_id": str(session.id),
            "issued_at": now_epoch,
            "events": [
                {"event_id": "rk2", "type": Event.Type.FOCUS_LOST, "occurred_at": timezone.now().isoformat()}
            ],
        },
        format="json",
        # Le SDK signe le MESSAGE avec la clé de chambre (pas la clé elle-même en en-tête).
        **machine_headers(message, signature=sign_message(room_key, message)),
    )
    assert response.status_code == 202
    assert response.data == {"accepted": 1, "duplicates": 0}


def test_close_signed_with_room_key(project, session, machine_headers, now_epoch):
    """La clôture aussi se signe avec la clé de chambre — dernier souffle de la clé."""
    room_key = derive_session_key(str(project.secret_key), str(session.id))
    message = f"{project.id}|{session.id}|{now_epoch}"
    response = APIClient().post(
        _close_url(session),
        {"invalid": False, "issued_at": now_epoch, "session_id": str(session.id)},
        format="json",
        **machine_headers(message, signature=sign_message(room_key, message)),
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ExamSession.Status.CLOSED


def test_foreign_room_key_is_401(project, session, other_project, machine_headers, now_epoch):
    """La clé de chambre d'un AUTRE projet ne valide rien : 401."""
    foreign_key = derive_session_key(str(other_project.secret_key), str(session.id))
    message = f"{project.id}|{session.id}|{now_epoch}"
    response = APIClient().post(
        EVENTS_URL,
        {
            "session_id": str(session.id),
            "issued_at": now_epoch,
            "events": [
                {"event_id": "rk3", "type": Event.Type.FOCUS_LOST, "occurred_at": timezone.now().isoformat()}
            ],
        },
        format="json",
        **machine_headers(message, signature=sign_message(foreign_key, message)),
    )
    assert response.status_code == 401


def test_room_key_of_another_session_is_401(project, session, machine_headers, now_epoch):
    """Clé dérivée pour un autre session_id (tentative de greffe) : la signature ne correspond pas."""
    other_room_key = derive_session_key(str(project.secret_key), "not-this-session")
    message = f"{project.id}|{session.id}|{now_epoch}"
    response = APIClient().post(
        EVENTS_URL,
        {
            "session_id": str(session.id),
            "issued_at": now_epoch,
            "events": [
                {"event_id": "rk4", "type": Event.Type.FOCUS_LOST, "occurred_at": timezone.now().isoformat()}
            ],
        },
        format="json",
        **machine_headers(message, signature=sign_message(other_room_key, message)),
    )
    assert response.status_code == 401
