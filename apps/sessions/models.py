"""
Modèle `ExamSession` — une session d'examen côté SDK (UC-5, 01_BACKEND.md §5.2, §9).

Une session est ouverte par le SDK quand un étudiant lance un examen : `POST
/api/v1/machine/sessions/` renvoie son identifiant, que le SDK réutilise ensuite pour envoyer
ses événements. Elle est fermée par `POST /api/v1/machine/sessions/{id}/close/` (UC-7).

Isolation multi-tenant : une session n'a pas de FK directe vers `Developer` (elle est rattachée
à un `Project`, qui porte le tenant). Le `TENANT_FIELD` du gestionnaire scopé pointe donc sur
`project__developer` (voir `apps/core/managers.py`).
"""

import uuid

from django.db import models

from apps.core.managers import TenantScopedQuerySet


class ExamSessionQuerySet(TenantScopedQuerySet):
    # Le tenant d'une session remonte par son projet : `ExamSession.objects.for_tenant(dev)`
    # filtre sur `project__developer`. Sans cette redéfinition, le filtre pointerait sur un
    # champ `developer` inexistant et lèverait une erreur de résolution de champ.
    TENANT_FIELD = "project__developer"


class ExamSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "active"
        # « Terminée » côté interface : la session s'est achevée normalement (close).
        CLOSED = "closed", "closed"
        # « Invalide » : session interrompue/compromise (jeton rejoué, fraude manifeste…).
        INVALID = "invalid", "invalid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="exam_sessions",
    )

    # Identifiants fournis par la plateforme du développeur (chaîne libre, jamais interprétée
    # comme un chemin : minimisation, 06_FRONTEND_GUIDE.md §11).
    exam_id = models.CharField(max_length=255, db_index=True)
    student_id = models.CharField(max_length=255, db_index=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )

    # Score de risque [0,1] calculé de façon asynchrone (Celery, étape 3). NULL tant que la
    # tâche n'a pas abouti : l'interface affiche « Calcul en cours » et non « 0 % » (BF-16).
    risk_score = models.FloatField(null=True, blank=True)

    # Horodatages de l'examen (fournis par le client, en UTC).
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Version du SDK émetteur (traçabilité ; utile si un comportement change selon la version).
    sdk_version = models.CharField(max_length=50, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Gestionnaire scopé : les vues dashboard appellent `for_tenant(developer)` — jamais un
    # `get(pk=...)` nu (isolation multi-tenant, 01_BACKEND.md §12).
    objects = models.Manager.from_queryset(ExamSessionQuerySet)()

    class Meta:
        verbose_name = "session d'examen"
        verbose_name_plural = "sessions d'examen"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "exam_id"]),
            models.Index(fields=["project", "-started_at"]),
        ]

    def __str__(self):
        return f"{self.exam_id} / {self.student_id}"

    @property
    def duration_seconds(self) -> int | None:
        """Durée écoulée en secondes : `ended_at - started_at` si terminée, sinon NULL.

        `started_at`/`ended_at` sont conscients du fuseau (USE_TZ) ; le formatage lisible
        (« 1 h 12 min ») est fait côté template par le filtre `duration`.
        """
        if not self.ended_at:
            return None
        return int((self.ended_at - self.started_at).total_seconds())
