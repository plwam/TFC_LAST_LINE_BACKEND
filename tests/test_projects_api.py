"""API JWT + cycle de vie des clés (01_BACKEND.md §10, UC-3) : JWT par email, reveal journalisé,
régénération invalidante, secret jamais exposé en série.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AccessLog
from apps.projects.services import KeyService

pytestmark = pytest.mark.django_db

TOKEN_URL = "/api/v1/auth/token/"


def _bearer(developer, password="pw12345!"):
    api = APIClient()
    response = api.post(TOKEN_URL, {"email": developer.user.email, "password": password}, format="json")
    assert response.status_code == 200, response.content
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api


def test_jwt_obtained_by_email(developer):
    response = APIClient().post(
        TOKEN_URL, {"email": developer.user.email, "password": "pw12345!"}, format="json"
    )
    assert response.status_code == 200
    assert "access" in response.data and "refresh" in response.data


def test_jwt_rejects_bad_password(developer):
    response = APIClient().post(
        TOKEN_URL, {"email": developer.user.email, "password": "nope"}, format="json"
    )
    assert response.status_code == 401


def test_api_projects_are_tenant_scoped(developer, other_developer, project, other_project):
    api = _bearer(developer)
    response = api.get("/api/v1/projects/")
    assert response.status_code == 200
    ids = {row["id"] for row in response.data}
    assert str(project.id) in ids
    assert str(other_project.id) not in ids


def test_api_project_detail_never_exposes_secret(developer, project):
    api = _bearer(developer)
    response = api.get(f"/api/v1/projects/{project.id}/")
    assert response.status_code == 200
    assert "secret_key" not in response.data
    assert response.data["public_key"] == project.public_key
    assert response.data["masked_secret"].endswith(project.secret_last4)


def test_reveal_is_no_store_and_audited(client, project):
    client.force_login(project.developer.user)
    response = client.post(reverse("dashboard:project-reveal-secret", args=[project.id]))
    assert response.status_code == 200
    assert response.json()["secret_key"] == project.secret_key
    assert "no-store" in response["Cache-Control"]
    assert AccessLog.objects.filter(action=AccessLog.Action.REVEAL_SECRET).count() == 1


def test_regenerate_invalidates_old_secret(client, project):
    old_secret = str(project.secret_key)
    client.force_login(project.developer.user)
    response = client.post(reverse("dashboard:project-regenerate-secret", args=[project.id]))
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.secret_key != old_secret
    assert AccessLog.objects.filter(action=AccessLog.Action.REGENERATE_SECRET).count() == 1


def test_secret_is_encrypted_at_rest(project):
    from django.db import connection

    # La valeur stockée en base ne doit PAS être le secret en clair (chiffrement au repos, §12).
    # SQLite stocke les UUID en hex 32 caractères sans tirets : on passe `project.id.hex`.
    with connection.cursor() as cursor:
        cursor.execute("SELECT secret_key FROM projects_project WHERE id = %s", [project.id.hex])
        row = cursor.fetchone()
    assert row is not None
    stored = row[0]
    assert stored != project.secret_key
    assert str(project.secret_key) not in stored


def test_key_service_generates_distinct_keys(project):
    first = project.public_key
    KeyService.generate_keys(project)
    project.refresh_from_db()
    assert project.public_key != first
    assert project.public_key.startswith("pk_live_")
    assert str(project.secret_key).startswith("sk_live_")
