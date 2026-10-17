"""Score de risque (BF-16) : borné, monotone, et recalculé par la tâche Celery."""

import pytest

from apps.events.models import Event
from apps.sessions.risk import compute_risk_score
from apps.sessions.tasks import compute_risk_score_task

pytestmark = pytest.mark.django_db


def _ev(event_type, confidence=None):
    # Instance non sauvegardée : `compute_risk_score` ne lit que `type` et `confidence_score`.
    return Event(type=event_type, confidence_score=confidence)


def test_empty_events_score_is_zero():
    assert compute_risk_score([]) == 0


def test_score_is_bounded_0_1():
    events = [_ev(Event.Type.AUTOMATION_DETECTED, 1.0) for _ in range(200)]
    assert 0 <= compute_risk_score(events) <= 1


def test_critical_weighs_more_than_benign():
    critical = compute_risk_score([_ev(Event.Type.AUTOMATION_DETECTED, 1.0)])
    benign = compute_risk_score([_ev(Event.Type.FOCUS_LOST)])
    assert critical > benign > 0


def test_low_confidence_lowers_score():
    high = compute_risk_score([_ev(Event.Type.GAZE_AWAY_SUSTAINED, 0.95)])
    low = compute_risk_score([_ev(Event.Type.GAZE_AWAY_SUSTAINED, 0.1)])
    assert high > low


def test_more_events_raise_score():
    one = compute_risk_score([_ev(Event.Type.TAB_SWITCH)])
    many = compute_risk_score([_ev(Event.Type.TAB_SWITCH) for _ in range(10)])
    assert many > one


def test_task_updates_session_score(session, make_event):
    for i in range(3):
        make_event(session, event_id=f"e{i}", event_type=Event.Type.AUTOMATION_DETECTED)
    result = compute_risk_score_task(str(session.id))
    session.refresh_from_db()
    assert result == session.risk_score
    assert session.risk_score > 0


def test_task_missing_session_returns_none():
    import uuid

    assert compute_risk_score_task(str(uuid.uuid4())) is None
