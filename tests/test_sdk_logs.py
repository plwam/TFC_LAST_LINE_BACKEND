"""Journal SDK : ingestion HMAC (heartbeat + logs), état en ligne/dégradé/hors ligne, dashboard.

Le SDK pousse un signal de vie (heartbeat) et des messages ; le dashboard en déduit l'état du
SDK à partir de la fraîcheur du dernier heartbeat (jamais d'une valeur déclarée par le client).
"""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.projects.services import ProjectService
from apps.sdklogs.models import SdkLog
from apps.sdklogs.status import compute_sdk_status
from apps.sessions.models import ExamSession

pytestmark = pytest.mark.django_db

LOGS_URL = "/api/v1/machine/logs/"


# ---------------------------------------------------------------------------
# Ingestion (API machine HMAC)
# ---------------------------------------------------------------------------


def _message(project, issued_at):
    # Canonique dédiée au journal : `project_id|sdk-logs|issued_at`.
    return f"{project.id}|sdk-logs|{issued_at}"


def test_ingest_creates_logs(project, machine_headers, now_epoch):
    response = APIClient().post(
        LOGS_URL,
        {
            "issued_at": now_epoch,
            "logs": [
                {"kind": "heartbeat", "level": "info"},
                {"kind": "log", "level": "error", "message": "Caméra indisponible."},
            ],
        },
        format="json",
        **machine_headers(_message(project, now_epoch)),
    )
    assert response.status_code == 202
    assert response.data == {"accepted": 2}
    assert SdkLog.objects.filter(project=project).count() == 2


def test_ingest_links_optional_session(project, session, machine_headers, now_epoch):
    APIClient().post(
        LOGS_URL,
        {"issued_at": now_epoch, "session_id": str(session.id), "logs": [{"kind": "heartbeat"}]},
        format="json",
        **machine_headers(_message(project, now_epoch)),
    )
    assert SdkLog.objects.get(project=project).session_id == session.id


def test_ingest_foreign_session_is_404(project, other_project, machine_headers, now_epoch):
    foreign = ExamSession.objects.create(
        project=other_project, exam_id="X", student_id="Y", started_at=timezone.now()
    )
    response = APIClient().post(
        LOGS_URL,
        {"issued_at": now_epoch, "session_id": str(foreign.id), "logs": [{"kind": "heartbeat"}]},
        format="json",
        **machine_headers(_message(project, now_epoch)),
    )
    assert response.status_code == 404
    assert SdkLog.objects.count() == 0


def test_ingest_bad_signature_is_401(project, machine_headers, now_epoch):
    response = APIClient().post(
        LOGS_URL,
        {"issued_at": now_epoch, "logs": [{"kind": "heartbeat"}]},
        format="json",
        **machine_headers("mauvaise-chainé"),
    )
    assert response.status_code == 401


def test_ingest_rejected_for_suspended_project(project, machine_headers, now_epoch):
    ProjectService.suspend_project(project)
    response = APIClient().post(
        LOGS_URL,
        {"issued_at": now_epoch, "logs": [{"kind": "heartbeat"}]},
        format="json",
        **machine_headers(_message(project, now_epoch)),
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# État du SDK (status.py)
# ---------------------------------------------------------------------------


def test_status_offline_without_logs(project):
    assert compute_sdk_status(project).state == "offline"


def test_status_online_with_fresh_heartbeat(project, make_sdk_log):
    make_sdk_log(project, kind="heartbeat")
    status = compute_sdk_status(project)
    assert status.state == "online"
    assert status.recent_errors == 0


def test_status_degraded_with_recent_error(project, make_sdk_log):
    make_sdk_log(project, kind="heartbeat")
    make_sdk_log(project, level="error", message="boom")
    assert compute_sdk_status(project).state == "degraded"


def test_status_offline_with_stale_heartbeat(project, make_sdk_log):
    make_sdk_log(
        project,
        kind="heartbeat",
        received_at=timezone.now() - timedelta(seconds=10000),
    )
    assert compute_sdk_status(project).state == "offline"


# ---------------------------------------------------------------------------
# Immuabilité (écriture seule)
# ---------------------------------------------------------------------------


def test_sdk_log_is_write_once(project, make_sdk_log):
    log = make_sdk_log(project, message="initial")
    log.message = "modifié"
    with pytest.raises(ValidationError):
        log.save()


# ---------------------------------------------------------------------------
# Dashboard : onglet « Journal SDK »
# ---------------------------------------------------------------------------


def test_logs_tab_renders_status_and_entries(client, project, make_sdk_log):
    make_sdk_log(project, kind="heartbeat", sdk_version="1.2.0")
    make_sdk_log(project, level="error", message="Caméra indisponible.")
    client.force_login(project.developer.user)

    html = client.get(
        reverse("dashboard:project-detail", args=[project.id]), {"tab": "logs"}
    ).content.decode()

    assert "Journal SDK" in html
    assert "Caméra indisponible." in html
    assert "Dégradé" in html  # heartbeat récent + erreur récente
    assert "data-sdk-log-stream" in html


def test_logs_tab_filters_by_level(client, project, make_sdk_log):
    make_sdk_log(project, level="info", message="info-msg")
    make_sdk_log(project, level="error", message="error-msg")
    client.force_login(project.developer.user)

    response = client.get(
        reverse("dashboard:project-detail", args=[project.id]),
        {"tab": "logs", "level": "error"},
    )
    assert [row["message"] for row in response.context["log_rows"]] == ["error-msg"]


def test_overview_shows_sdk_status(client, project, make_sdk_log):
    make_sdk_log(project, kind="heartbeat")
    client.force_login(project.developer.user)
    html = client.get(
        reverse("dashboard:project-detail", args=[project.id]), {"tab": "overview"}
    ).content.decode()
    assert "État du SDK" in html


# ---------------------------------------------------------------------------
# Flux temps réel (feed JSON) + isolation
# ---------------------------------------------------------------------------


def test_logs_feed_returns_status_and_logs(client, project, make_sdk_log):
    make_sdk_log(project, kind="heartbeat")
    make_sdk_log(project, level="error", message="boom")
    client.force_login(project.developer.user)

    data = client.get(reverse("dashboard:project-logs-feed", args=[project.id])).json()
    assert data["status"]["state"] == "degraded"
    assert data["status"]["label"] == "Dégradé"
    assert len(data["logs"]) == 2
    assert {"level_label", "kind_label", "received_at"} <= set(data["logs"][0].keys())


def test_logs_feed_since_returns_only_newer(client, project, make_sdk_log):
    old = make_sdk_log(
        project, message="ancien", received_at=timezone.now() - timedelta(minutes=5)
    )
    make_sdk_log(project, message="nouveau")
    client.force_login(project.developer.user)

    data = client.get(
        reverse("dashboard:project-logs-feed", args=[project.id]),
        {"since": old.received_at.isoformat()},
    ).json()
    assert [row["message"] for row in data["logs"]] == ["nouveau"]


def test_logs_feed_of_other_tenant_is_404(client, project, other_project, make_sdk_log):
    make_sdk_log(other_project, message="secret-autre-projet")
    client.force_login(project.developer.user)
    response = client.get(reverse("dashboard:project-logs-feed", args=[other_project.id]))
    assert response.status_code == 404


def test_logs_tab_of_other_tenant_is_404(client, project, other_project):
    client.force_login(project.developer.user)
    response = client.get(
        reverse("dashboard:project-detail", args=[other_project.id]), {"tab": "logs"}
    )
    assert response.status_code == 404
