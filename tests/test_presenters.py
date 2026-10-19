"""Presenter des événements (06_FRONTEND_GUIDE.md §9) : parité, défensivité, formatage FR.

Règle XSS : le presenter ne renvoie QUE du texte brut ; c'est l'auto-échappement Django à
l'affichage qui protège. On vérifie donc que le contenu dangereux est bien échappé dans le HTML
rendu.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.presenters import (
    EVENT_PRESENTATION,
    EventPresentation,
    label_for_type,
    present_event,
)
from apps.events.models import Event

pytestmark = pytest.mark.django_db


def test_presentation_covers_all_types():
    # Parité stricte entre le catalogue technique et la table d'affichage : si un type est
    # ajouté au modèle sans phrase, ce test échoue (contrat partagé, 05_AGENT_GUIDELINES.md §5).
    assert set(EVENT_PRESENTATION.keys()) == set(Event.Type.values)
    assert len(EVENT_PRESENTATION) == 29


def test_present_event_french_formatting():
    event = Event(
        type=Event.Type.GAZE_AWAY_SUSTAINED,
        metadata={"durationMs": 3400, "gaze": {"yawDeg": 32, "pitchDeg": 5}},
    )
    presentation = present_event(event)
    assert presentation == EventPresentation(
        label="Regard détourné",
        category="vision",
        sentence="Regard détourné pendant 3,4 s (angle horizontal 32°, vertical 5°).",
        critical=False,
    )


def test_present_event_is_defensive_on_bad_metadata():
    # Aucune de ces métadonnées mal typées ne doit lever (contrat défensif §9).
    for bad in [None, [], "oops", {"durationMs": "abc"}, {"gaze": "not-a-dict"}, {"count": "x"}]:
        event = Event(type=Event.Type.GAZE_AWAY_SUSTAINED, metadata=bad)
        assert isinstance(present_event(event).sentence, str)


def test_unknown_type_falls_back_to_raw_name():
    event = Event(type="FUTURE_EVENT_FROM_SDK", metadata={})
    presentation = present_event(event)
    assert presentation.label == "FUTURE_EVENT_FROM_SDK"
    assert presentation.critical is False
    assert label_for_type("FUTURE_EVENT_FROM_SDK") == "FUTURE_EVENT_FROM_SDK"


def test_critical_flag_matches_catalog():
    critical = present_event(Event(type=Event.Type.AUTOMATION_DETECTED, metadata={}))
    benign = present_event(Event(type=Event.Type.FOCUS_LOST, metadata={}))
    assert critical.critical is True
    assert benign.critical is False


def test_metadata_is_escaped_in_dashboard(client, developer, session, make_event):
    payload = "<script>alert('xss')</script>"
    make_event(
        session,
        event_id="xss",
        event_type=Event.Type.FORBIDDEN_OBJECT_DETECTED,
        metadata={"label": payload, "confidence": 0.9},
        occurred_at=timezone.now(),
    )
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:session-detail", args=[session.id]))
    html = response.content.decode()
    assert response.status_code == 200
    # La charge utile est présente… mais ÉCHAPPÉE : jamais exécutable.
    assert "<script>alert('xss')</script>" not in html
    assert "&lt;script&gt;" in html
