"""
Fixtures partagées de la suite `tests/` (04_TESTS.md — non accessible : plan reconstruit).

Aucune logique métier ici : on fabrique des DEVELOPPEURS, PROJETS, SESSIONS et ÉVÉNEMENTS
réalistes via les mêmes services que l'application (`ProjectService`), pour que les tests
exercent le vrai chemin de création (génération des clés, audit).
"""

import time

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.hmac import sign_message
from apps.developers.models import Developer
from apps.events.models import Event
from apps.projects.services import ProjectService
from apps.sessions.models import ExamSession

# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


@pytest.fixture
def make_developer(db):
    """Fabrique un couple User + Developer avec un statut donné."""

    def _make(email, status=Developer.Status.ACTIVE, full_name="Dev Test", password="pw12345!"):
        user = get_user_model().objects.create_user(
            username=email, email=email, password=password
        )
        # Le signal allauth crée le profil à l'inscription ; ici on passe par `create_user`,
        # donc on crée le profil explicitement (même résultat métier).
        developer = Developer.objects.create(user=user, full_name=full_name, status=status)
        return developer

    return _make


@pytest.fixture
def developer(make_developer):
    return make_developer("dev@example.com")


@pytest.fixture
def other_developer(make_developer):
    return make_developer("other@example.com")


@pytest.fixture
def project(developer):
    return ProjectService.create_project(
        developer, "Projet A", "Description", "https://examens.univ-a.edu"
    )


@pytest.fixture
def other_project(other_developer):
    return ProjectService.create_project(
        other_developer, "Projet B", "Description", "https://examens.univ-b.edu"
    )


@pytest.fixture
def session(project):
    return ExamSession.objects.create(
        project=project,
        exam_id="EXAM-1",
        student_id="STU-1",
        started_at=timezone.now(),
    )


@pytest.fixture
def make_event(db):
    """Fabrique un `Event` pour une session donnée (write-once)."""

    def _make(session, event_type=Event.Type.FOCUS_LOST, event_id=None, source=Event.Source.SDK,
              confidence_score=None, metadata=None, occurred_at=None):
        return Event.objects.create(
            session=session,
            event_id=event_id or f"evt-{time.time_ns()}",
            type=event_type,
            source=source,
            confidence_score=confidence_score,
            metadata=metadata or {},
            occurred_at=occurred_at or timezone.now(),
        )

    return _make


# ---------------------------------------------------------------------------
# Signature HMAC de l'API machine
# ---------------------------------------------------------------------------


@pytest.fixture
def machine_headers(project):
    """Construit les en-têtes HMAC attendus par `HMACAuthentication`.

    `message` est la chaîne canonique :
      - création de session : `project_id|exam_id|student_id|issued_at` ;
      - envoi d'événements   : `project_id|session_id|issued_at`.
    """

    def _make(message, public_key=None, signature=None):
        return {
            "HTTP_X_EXAMSDK_PUBLIC_KEY": public_key or project.public_key,
            "HTTP_X_EXAMSDK_SIGNATURE": signature
            if signature is not None
            else sign_message(str(project.secret_key), message),
        }

    return _make


@pytest.fixture
def now_epoch():
    return int(time.time())
