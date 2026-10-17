"""Isolation multi-tenant (01_BACKEND.md §12) : un développeur ne voit JAMAIS les données d'un autre.

Règle : ressource d'un autre tenant → 404 (et non 403), pour ne pas révéler son existence.
"""

import pytest
from django.urls import reverse

from apps.events.models import Event
from apps.sessions.models import ExamSession

pytestmark = pytest.mark.django_db


def test_project_list_excludes_other_tenants(client, developer, project, other_project):
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:project-list"))
    assert response.status_code == 200
    assert project in response.context["projects"]
    assert other_project not in response.context["projects"]


def test_project_detail_other_tenant_is_404(client, developer, other_project):
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:project-detail", args=[other_project.id]))
    assert response.status_code == 404


def test_session_detail_other_tenant_is_404(client, developer, other_project):
    from django.utils import timezone

    foreign_session = ExamSession.objects.create(
        project=other_project, exam_id="X", student_id="Y", started_at=timezone.now()
    )
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:session-detail", args=[foreign_session.id]))
    assert response.status_code == 404


def test_tenant_scoped_manager_filters(make_event, developer, project, other_project, session):
    from django.utils import timezone

    foreign_session = ExamSession.objects.create(
        project=other_project, exam_id="X", student_id="Y", started_at=timezone.now()
    )
    make_event(session, event_id="mine")
    make_event(foreign_session, event_id="theirs")

    mine = Event.objects.for_tenant(developer)
    assert mine.count() == 1
    assert mine.first().event_id == "mine"
