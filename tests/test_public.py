"""API publique (01_BACKEND.md §11) : hôtes autorisés + minimisation (jamais de clé/ID)."""

import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.projects.services import ProjectService

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_registered_hosts_lists_domains(client, project):
    response = client.get(reverse("public:registered-hosts"))
    assert response.status_code == 200
    assert response.json() == {"hosts": ["examens.univ-a.edu"], "count": 1}


def test_registered_hosts_excludes_archived(client, project):
    ProjectService.archive_project(project)
    response = client.get(reverse("public:registered-hosts"))
    assert response.json()["count"] == 0


def test_registered_hosts_deduplicates(client, developer, project):
    ProjectService.create_project(developer, "Autre", "", "https://examens.univ-a.edu/autre")
    response = client.get(reverse("public:registered-hosts"))
    assert response.json()["hosts"] == ["examens.univ-a.edu"]


def test_registered_hosts_never_leaks_keys(client, project):
    body = client.get(reverse("public:registered-hosts")).content.decode()
    assert project.public_key not in body
    assert str(project.secret_key) not in body
    assert str(project.id) not in body


def test_health(client):
    response = client.get("/public/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
