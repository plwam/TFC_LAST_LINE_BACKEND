"""
Modèle `SdkLog` — journal de fonctionnement du SDK (rubrique « Journal SDK » du dashboard).

Le SDK embarqué dans la page d'examen pousse vers ExamSDK deux familles d'entrées :
  - des HEARTBEATS (`kind=heartbeat`) : un signal de vie périodique, qui permet au développeur
    de savoir que son SDK tourne — et, par ABSENCE de signal, qu'il ne tourne plus ;
  - des LOGS applicatifs (`kind=log`) : messages de fonctionnement / erreurs, avec un niveau.

Ce sont des données de TÉLÉMÉTRIE de diagnostic, pas une preuve légale : contrairement aux
`Event` (immuables et conservés, BNF-33), un `SdkLog` pourra être purgé par une tâche de
rétention. Il reste néanmoins en ÉCRITURE SEULE au niveau applicatif : on n'écrase jamais une
entrée de journal (voir `save`).

Isolation multi-tenant : un log n'a pas de FK directe vers `Developer` (il est rattaché à un
`Project`, qui porte le tenant). Le `TENANT_FIELD` du gestionnaire scopé pointe donc sur
`project__developer` (voir `apps/core/managers.py`).

Sécurité : `context` provient du client (navigateur/SDK) et n'est PAS digne de confiance. Il
n'est jamais interprété côté serveur et jamais affiché avec `|safe` (même règle que
`Event.metadata`, 06_FRONTEND_GUIDE.md §11).
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.managers import TenantScopedQuerySet


class SdkLogQuerySet(TenantScopedQuerySet):
    # Le tenant d'un log remonte par son projet : `SdkLog.objects.for_tenant(dev)` filtre sur
    # `project__developer`.
    TENANT_FIELD = "project__developer"


class SdkLog(models.Model):
    class Level(models.TextChoices):
        # Du plus verbeux au plus grave. `error` alimente la notion d'état « dégradé ».
        DEBUG = "debug", "debug"
        INFO = "info", "info"
        WARNING = "warning", "warning"
        ERROR = "error", "error"

    class Kind(models.TextChoices):
        # Signal de vie périodique (permet de conclure en ligne / hors ligne).
        HEARTBEAT = "heartbeat", "heartbeat"
        # Message de journal applicatif (fonctionnement, avertissement, erreur…).
        LOG = "log", "log"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="sdk_logs",
    )
    # Session facultative : un log peut viser une passation précise, sans l'exiger (les
    # heartbeats de mise en route peuvent précéder l'ouverture de session). SET_NULL : purger
    # une session ne doit pas effacer le journal du SDK.
    session = models.ForeignKey(
        "examsessions.ExamSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sdk_logs",
    )

    level = models.CharField(
        max_length=20, choices=Level.choices, default=Level.INFO, db_index=True
    )
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.LOG, db_index=True
    )

    message = models.TextField(blank=True, default="")
    sdk_version = models.CharField(max_length=50, blank=True, default="")

    # Métadonnées brutes NON fiables (viennent du SDK / navigateur étudiant) : jamais affichées
    # avec `|safe`, jamais interprétées côté serveur.
    context = models.JSONField(default=dict, blank=True)

    # `occurred_at` = horodatage côté SDK ; `received_at` = réception serveur. L'état en
    # ligne/hors ligne se calcule UNIQUEMENT sur `received_at` (un client ne peut pas mentir
    # sur l'heure d'arrivée au serveur).
    occurred_at = models.DateTimeField(db_index=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = models.Manager.from_queryset(SdkLogQuerySet)()

    class Meta:
        verbose_name = "entrée du journal SDK"
        verbose_name_plural = "journal du SDK"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["project", "-received_at"]),
            models.Index(fields=["project", "level"]),
            models.Index(fields=["project", "kind"]),
        ]

    def __str__(self):
        return f"{self.level}/{self.kind} @ {self.received_at:%Y-%m-%d %H:%M:%S}"

    def save(self, *args, **kwargs):
        """Interdit la modification d'une entrée existante (journal en écriture seule).

        Un log est un enregistrement de ce qui s'est passé : le réécrire fausserait le
        diagnostic. La purge (rétention) reste possible via une opération privilégiée
        (`queryset.delete()`), jamais une écriture de vue.
        """
        if not self._state.adding:
            raise ValidationError(
                "Une entrée du journal SDK est en écriture seule : elle ne peut pas être modifiée."
            )
        return super().save(*args, **kwargs)
