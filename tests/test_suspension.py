"""Suspension d'un compte (UC-12, 06_FRONTEND_GUIDE.md §7) : lecture autorisée, écriture refusée.

La protection réelle est côté serveur (403) ; le masquage des boutons dans le template n'est
qu'un confort visuel.
"""

import pytest
from django.urls import reverse

from apps.audit.models import AccessLog
from apps.developers.models import Developer

pytestmark = pytest.mark.django_db


def test_suspended_can_read_dashboard(client, make_developer):
    dev = make_developer("susp@example.com", status=Developer.Status.SUSPENDED)
    client.force_login(dev.user)
    assert client.get(reverse("dashboard:home")).status_code == 200


def test_suspended_cannot_reveal_secret(client, project):
    project.developer.status = Developer.Status.SUSPENDED
    project.developer.save(update_fields=["status"])
    client.force_login(project.developer.user)
    response = client.post(reverse("dashboard:project-reveal-secret", args=[project.id]))
    assert response.status_code == 403
    # Aucun secret ne doit fuiter, et aucune entrée d'audit ne doit être écrite pour un refus.
    assert AccessLog.objects.filter(action=AccessLog.Action.REVEAL_SECRET).count() == 0


def test_suspended_cannot_create_project(client, make_developer):
    dev = make_developer("susp2@example.com", status=Developer.Status.SUSPENDED)
    client.force_login(dev.user)
    response = client.post(
        reverse("dashboard:project-create"),
        {"name": "X", "description": "", "site_url": "https://x.edu"},
    )
    assert response.status_code == 403


def test_pending_can_still_create_project(client, make_developer):
    dev = make_developer("pending@example.com", status=Developer.Status.PENDING)
    client.force_login(dev.user)
    response = client.post(
        reverse("dashboard:project-create"),
        {"name": "Projet Pending", "description": "", "site_url": "https://x.edu"},
    )
    assert response.status_code == 302
