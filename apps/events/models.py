"""
Modèle `Event` — événement de surveillance (UC-10, BNF-33, 01_BACKEND.md §5.2).

IMMUABILITÉ (BNF-33) : un événement est une preuve. Il n'est jamais modifié ni supprimé après
création. Deux niveaux de protection :
  1. applicatif (ici) : `save()` refuse toute mise à jour d'une ligne existante et `delete()`
     est bloqué — un bug de vue ne peut donc pas réécrire l'historique ;
  2. base de données (production MySQL) : privilège `DELETE` révoqué sur la table `events`
     (01_BACKEND.md §12). Ce deuxième niveau n'existe pas en SQLite de développement.

Le contrat d'événement (liste des `EventType`, champs de `metadata`) est partagé avec le SDK
(`00_PROJECT_OVERVIEW.md` §7) : toute évolution doit être répercutée dans les trois modules
(05_AGENT_GUIDELINES.md §5).
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.managers import TenantScopedQuerySet


class EventQuerySet(TenantScopedQuerySet):
    # Tenant d'un événement : il remonte par `session → project → developer`.
    TENANT_FIELD = "session__project__developer"


class Event(models.Model):
    class Source(models.TextChoices):
        # Émis par le SDK embarqué dans la page d'examen (détecteurs navigateur/vision/audio).
        SDK = "sdk", "sdk"
        # Émis par l'extension navigateur (onglets, navigation, environnement).
        EXTENSION = "extension", "extension"

    class Type(models.TextChoices):
        # --- Navigateur (SDK) ---
        FOCUS_LOST = "FOCUS_LOST", "FOCUS_LOST"
        TAB_SWITCH = "TAB_SWITCH", "TAB_SWITCH"
        COPY_PASTE_TEXT = "COPY_PASTE_TEXT", "COPY_PASTE_TEXT"
        CLIPBOARD_IMAGE_PASTE = "CLIPBOARD_IMAGE_PASTE", "CLIPBOARD_IMAGE_PASTE"
        PAGE_EXIT = "PAGE_EXIT", "PAGE_EXIT"
        DOM_TAMPERING = "DOM_TAMPERING", "DOM_TAMPERING"
        DEVTOOLS_OPEN = "DEVTOOLS_OPEN", "DEVTOOLS_OPEN"
        FULLSCREEN_EXIT = "FULLSCREEN_EXIT", "FULLSCREEN_EXIT"
        PRINT_ATTEMPT = "PRINT_ATTEMPT", "PRINT_ATTEMPT"
        SUSPICIOUS_KEY_COMBO = "SUSPICIOUS_KEY_COMBO", "SUSPICIOUS_KEY_COMBO"
        IDLE_TIMEOUT = "IDLE_TIMEOUT", "IDLE_TIMEOUT"
        MULTI_MONITOR_DETECTED = "MULTI_MONITOR_DETECTED", "MULTI_MONITOR_DETECTED"

        # --- Sécurité (SDK / extension) ---
        AUTOMATION_DETECTED = "AUTOMATION_DETECTED", "AUTOMATION_DETECTED"
        EXTENSION_HEARTBEAT_LOST = "EXTENSION_HEARTBEAT_LOST", "EXTENSION_HEARTBEAT_LOST"
        SIMULATED_EVENT_DETECTED = "SIMULATED_EVENT_DETECTED", "SIMULATED_EVENT_DETECTED"

        # --- Vision (SDK) ---
        NO_FACE_DETECTED = "NO_FACE_DETECTED", "NO_FACE_DETECTED"
        MULTIPLE_FACES = "MULTIPLE_FACES", "MULTIPLE_FACES"
        FORBIDDEN_OBJECT_DETECTED = "FORBIDDEN_OBJECT_DETECTED", "FORBIDDEN_OBJECT_DETECTED"
        VIRTUAL_DEVICE_DETECTED = "VIRTUAL_DEVICE_DETECTED", "VIRTUAL_DEVICE_DETECTED"
        GAZE_AWAY_SUSTAINED = "GAZE_AWAY_SUSTAINED", "GAZE_AWAY_SUSTAINED"
        REPEATED_HEAD_TURN = "REPEATED_HEAD_TURN", "REPEATED_HEAD_TURN"
        HANDS_VISIBLE_SUSTAINED = "HANDS_VISIBLE_SUSTAINED", "HANDS_VISIBLE_SUSTAINED"

        # --- Audio (SDK) ---
        AUDIO_KEYWORD_MATCH = "AUDIO_KEYWORD_MATCH", "AUDIO_KEYWORD_MATCH"
        MULTIPLE_VOICES = "MULTIPLE_VOICES", "MULTIPLE_VOICES"

        # --- Extension ---
        TAB_CHANGE_EXT = "TAB_CHANGE_EXT", "TAB_CHANGE_EXT"
        NAVIGATION_EXT = "NAVIGATION_EXT", "NAVIGATION_EXT"
        SUSPICIOUS_ENVIRONMENT = "SUSPICIOUS_ENVIRONMENT", "SUSPICIOUS_ENVIRONMENT"

        # --- Retour candidat / interface (SDK) ---
        # Émis par le SDK : avertissement vocal/bandeau prononcé au candidat, et retrait/masquage
        # de l'aperçu ou du bandeau de surveillance (02b_SDK_RETOUR_CANDIDAT.md §4).
        WARNING_ISSUED = "WARNING_ISSUED", "WARNING_ISSUED"
        UI_TAMPERING = "UI_TAMPERING", "UI_TAMPERING"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        "examsessions.ExamSession",
        on_delete=models.CASCADE,
        related_name="events",
    )

    # Identifiant fourni par le client (SDK/extension) : permet l'IDEMPOTENCE — un renvoi
    # réseau du même événement ne crée pas de doublon (contrainte d'unicité ci-dessous).
    event_id = models.CharField(max_length=128)

    type = models.CharField(max_length=40, choices=Type.choices, db_index=True)
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.SDK, db_index=True
    )

    # Confiance [0,1] renvoyée par le détecteur (vision/audio). NULL si non applicable.
    confidence_score = models.FloatField(null=True, blank=True)

    sdk_version = models.CharField(max_length=50, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    # Empreinte d'intégrité du lot d'événements (détection de falsification en transit).
    integrity_hash = models.CharField(max_length=128, blank=True, default="")

    # Métadonnées brutes NON fiables (viennent du navigateur étudiant). Jamais affichées avec
    # `|safe` ; jamais interprétées côté serveur (06_FRONTEND_GUIDE.md §11).
    metadata = models.JSONField(default=dict, blank=True)

    # `occurred_at` = horodatage de détection (client) ; `received_at` = réception serveur.
    # Les deux sont conservés : un écart anormal peut lui-même être un signal.
    occurred_at = models.DateTimeField(db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(EventQuerySet)()

    class Meta:
        verbose_name = "événement"
        verbose_name_plural = "événements"
        ordering = ["occurred_at"]
        indexes = [
            models.Index(fields=["session", "occurred_at"]),
            models.Index(fields=["session", "type"]),
        ]
        constraints = [
            # Idempotence par session : (session, event_id) unique.
            models.UniqueConstraint(fields=["session", "event_id"], name="uniq_event_per_session"),
        ]

    def __str__(self):
        return f"{self.type} @ {self.occurred_at:%Y-%m-%d %H:%M:%S}"

    def save(self, *args, **kwargs):
        """Interdit toute modification d'un événement existant (immuabilité applicative, BNF-33)."""
        if not self._state.adding:
            raise ValidationError(
                "Un événement est immuable : il ne peut pas être modifié après création."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Interdit la suppression d'un événement.

        La purge éventuelle (rétention) est une opération de maintenance privilégiée distincte,
        jamais une action d'interface (06_FRONTEND_GUIDE.md §8.8).
        """
        raise ValidationError(
            "Un événement est immuable : sa suppression directe est interdite."
        )
