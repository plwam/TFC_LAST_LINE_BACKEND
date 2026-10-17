"""Cycle de vie d'un projet (actif / suspendu / désactivé) : services, dashboard, HMAC et filtres.

Un projet suspendu ou désactivé reste visible dans le dashboard mais ses clés HMAC sont refusées
(comme un projet archivé) ; l'opération est réversible et journalisée.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AccessLog
from apps.developers.models import Developer
from apps.projects.models import Project
from apps.projects.services import ProjectService

pytestmark = pytest.mark.django_db

CREATE_URL = "/api/v1/machine/sessions/"


# ---------------------------------------------------------------------------
# Service (logique métier + audit)
# ---------------------------------------------------------------------------


def test_suspend_project_sets_status_and_audits(project):
    ProjectService.suspend_project(project)
    project.refresh_from_db()
    assert project.status == Project.Status.SUSPENDED
    assert project.is_suspended is True
    assert project.accepts_traffic is False
    assert AccessLog.objects.filter(action=AccessLog.Action.SUSPEND_PROJECT).count() == 1


def test_disable_project_sets_status_and_audits(project):
    ProjectService.disable_project(project)
    project.refresh_from_db()
    assert project.status == Project.Status.DISABLED
    assert AccessLog.objects.filter(action=AccessLog.Action.DISABLE_PROJECT).count() == 1


def test_reactivate_project_restores_active(project):
    ProjectService.suspend_project(project)
    ProjectService.reactivate_project(project)
    project.refresh_from_db()
    assert project.status == Project.Status.ACTIVE
    assert project.accepts_traffic is True
    assert AccessLog.objects.filter(action=AccessLog.Action.REACTIVATE_PROJECT).count() == 1


# ---------------------------------------------------------------------------
# Dashboard (actions du développeur)
# ---------------------------------------------------------------------------


def test_developer_can_suspend_own_project(client, project):
    client.force_login(project.developer.user)
    response = client.post(reverse("dashboard:project-suspend", args=[project.id]))
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.status == Project.Status.SUSPENDED


def test_developer_can_disable_then_reactivate(client, project):
    client.force_login(project.developer.user)
    client.post(reverse("dashboard:project-disable", args=[project.id]))
    project.refresh_from_db()
    assert project.status == Project.Status.DISABLED
    client.post(reverse("dashboard:project-reactivate", args=[project.id]))
    project.refresh_from_db()
    assert project.status == Project.Status.ACTIVE


def test_cannot_change_status_of_other_tenant_project(client, developer, other_project):
    client.force_login(developer.user)
    response = client.post(reverse("dashboard:project-suspend", args=[other_project.id]))
    assert response.status_code == 404
    other_project.refresh_from_db()
    assert other_project.status == Project.Status.ACTIVE


def test_suspended_developer_cannot_change_status(client, project):
    developer = project.developer
    developer.status = Developer.Status.SUSPENDED
    developer.save(update_fields=["status"])
    client.force_login(developer.user)
    response = client.post(reverse("dashboard:project-suspend", args=[project.id]))
    assert response.status_code == 403
    project.refresh_from_db()
    assert project.status == Project.Status.ACTIVE


def test_project_list_shows_status_badge(client, project):
    client.force_login(project.developer.user)
    ProjectService.suspend_project(project)
    html = client.get(reverse("dashboard:project-list")).content.decode()
    assert "Suspendu" in html


# ---------------------------------------------------------------------------
# HMAC : les clés d'un projet suspendu/désactivé sont refusées
# ---------------------------------------------------------------------------


def _machine_call(project, machine_headers, now_epoch):
    message = f"{project.id}|E|S|{now_epoch}"
    return APIClient().post(
        CREATE_URL,
        {"exam_id": "E", "student_id": "S", "issued_at": now_epoch},
        format="json",
        **machine_headers(message),
    )


def test_suspended_project_keys_are_rejected(project, machine_headers, now_epoch):
    ProjectService.suspend_project(project)
    assert _machine_call(project, machine_headers, now_epoch).status_code == 401


def test_disabled_project_keys_are_rejected(project, machine_headers, now_epoch):
    ProjectService.disable_project(project)
    assert _machine_call(project, machine_headers, now_epoch).status_code == 401


def test_reactivated_project_keys_are_accepted(project, machine_headers, now_epoch):
    ProjectService.suspend_project(project)
    ProjectService.reactivate_project(project)
    assert _machine_call(project, machine_headers, now_epoch).status_code == 201


# ---------------------------------------------------------------------------
# Filtres de la liste (état + période de création)
# ---------------------------------------------------------------------------


def test_project_list_filters_by_status(client, developer, project):
    client.force_login(developer.user)
    active_project = ProjectService.create_project(developer, "Actif", "", "https://actif.edu")
    ProjectService.suspend_project(project)

    suspended = client.get(reverse("dashboard:project-list"), {"status": "suspended"})
    assert list(suspended.context["projects"]) == [project]

    active = client.get(reverse("dashboard:project-list"), {"status": "active"})
    assert list(active.context["projects"]) == [active_project]


def test_project_list_filters_by_creation_date(client, developer, project):
    from datetime import timedelta

    from django.utils import timezone

    Project.objects.filter(pk=project.pk).update(
        created_at=timezone.now() - timedelta(days=30)
    )
    client.force_login(developer.user)

    future = client.get(
        reverse("dashboard:project-list"),
        {"date_from": timezone.localdate().isoformat()},
    )
    assert list(future.context["projects"]) == []

    wide = client.get(
        reverse("dashboard:project-list"),
        {"date_to": timezone.localdate().isoformat()},
    )
    assert project in wide.context["projects"]
