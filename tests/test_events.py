"""Immuabilité des événements (BNF-33) : write-once, no-delete, idempotence par (session, event_id)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.events.models import Event

pytestmark = pytest.mark.django_db


def test_event_cannot_be_updated(session, make_event):
    event = make_event(session, event_id="a")
    event.metadata = {"tampered": True}
    with pytest.raises(ValidationError):
        event.save()


def test_event_cannot_be_deleted(session, make_event):
    event = make_event(session, event_id="a")
    with pytest.raises(ValidationError):
        event.delete()
    assert Event.objects.filter(pk=event.pk).exists()


def test_event_id_unique_per_session(session, make_event):
    make_event(session, event_id="dup")
    with pytest.raises(IntegrityError), transaction.atomic():
        Event.objects.create(
            session=session,
            event_id="dup",
            type=Event.Type.FOCUS_LOST,
            occurred_at=timezone.now(),
        )


def test_same_event_id_allowed_on_other_session(project, other_project, session, make_event):
    from apps.sessions.models import ExamSession

    other_session = ExamSession.objects.create(
        project=other_project, exam_id="X", student_id="Y", started_at=timezone.now()
    )
    make_event(session, event_id="same")
    make_event(other_session, event_id="same")  # pas de collision : scoping par session
    assert Event.objects.filter(event_id="same").count() == 2
