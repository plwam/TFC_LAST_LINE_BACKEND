"""Django Admin (UC-11..13) : accès réservé au staff, actions de modération journalisées,
événements en lecture seule, vue de métriques.
"""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.audit.models import AccessLog
from apps.developers.models import Developer
from apps.events.admin import EventAdmin
from apps.events.models import Event

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(make_developer):
    user = get_user_model().objects.create_superuser(
        username="root@example.com", email="root@example.com", password="pw12345!"
    )
    return user


def test_admin_requires_staff(client, developer):
    client.force_login(developer.user)
    response = client.get("/admin/")
    assert response.status_code == 302  # redirigé vers la connexion admin


def test_staff_can_reach_admin_and_metrics(client, staff):
    client.force_login(staff)
    assert client.get("/admin/").status_code == 200
    response = client.get(reverse("admin-metrics"))
    assert response.status_code == 200
    assert "triques" in response.content.decode()  # « Métriques »


def test_event_admin_is_read_only():
    event_admin = admin.site._registry[Event]
    assert isinstance(event_admin, EventAdmin)
    request = None  # les permissions ne consultent pas la requête pour ces modèles
    assert event_admin.has_add_permission(request) is False
    assert event_admin.has_change_permission(request) is False
    assert event_admin.has_delete_permission(request) is False


def test_developer_admin_approve_action_audits(client, staff, make_developer):
    dev = make_developer("mod@example.com", status=Developer.Status.PENDING)
    client.force_login(staff)
    response = client.post(
        reverse("admin:developers_developer_changelist"),
        {
            "action": "approve_selected",
            "_selected_action": [str(dev.pk)],
            "index": "0",
        },
    )
    assert response.status_code == 302
    dev.refresh_from_db()
    assert dev.status == Developer.Status.ACTIVE
    assert AccessLog.objects.filter(
        action=AccessLog.Action.VALIDATE_DEVELOPER, developer=dev
    ).count() == 1


def test_developer_admin_suspend_action(client, staff, make_developer):
    dev = make_developer("mod2@example.com", status=Developer.Status.ACTIVE)
    client.force_login(staff)
    client.post(
        reverse("admin:developers_developer_changelist"),
        {"action": "suspend_selected", "_selected_action": [str(dev.pk)], "index": "0"},
    )
    dev.refresh_from_db()
    assert dev.status == Developer.Status.SUSPENDED
    assert AccessLog.objects.filter(action=AccessLog.Action.SUSPEND_DEVELOPER).count() == 1


def test_admin_developer_list_shows_email(client, staff, make_developer):
    dev = make_developer("listed@example.com")
    client.force_login(staff)
    response = client.get(reverse("admin:developers_developer_changelist"))
    assert response.status_code == 200
    assert b"listed@example.com" in response.content
