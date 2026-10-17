"""
Journal d'audit — `AccessLog` (BNF-33, 01_BACKEND.md §8.8).

Trace les actions sensibles (révélation/régénération de clé) et les consultations de données
(projet, session). Immuable en pratique : on écrit, on ne modifie jamais — la seule opération
d'admin prévue est la lecture (filtres par acteur/action/date).
"""

import uuid

from django.conf import settings
from django.db import models


class AccessLog(models.Model):
    class Action(models.TextChoices):
        CREATE_PROJECT = "create_project", "create_project"
        UPDATE_PROJECT = "update_project", "update_project"
        DELETE_PROJECT = "delete_project", "delete_project"
        # Cycle de vie d'un projet : suspension / désactivation / réactivation (réversible).
        SUSPEND_PROJECT = "suspend_project", "suspend_project"
        DISABLE_PROJECT = "disable_project", "disable_project"
        REACTIVATE_PROJECT = "reactivate_project", "reactivate_project"
        REGENERATE_SECRET = "regenerate_secret", "regenerate_secret"
        REVEAL_SECRET = "reveal_secret", "reveal_secret"
        CONSULTATION = "consultation", "consultation"
        # Actions d'administration (UC-12) : validation/suspension en masse d'un développeur.
        VALIDATE_DEVELOPER = "validate_developer", "validate_developer"
        SUSPEND_DEVELOPER = "suspend_developer", "suspend_developer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Acteur humain (nullable : certaines actions peuvent être déclenchées sans session).
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="access_logs",
    )
    # Développeur concerné (permet de filtrer l'audit par tenant côté admin).
    developer = models.ForeignKey(
        "developers.Developer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="access_logs",
    )

    action = models.CharField(max_length=40, choices=Action.choices)
    # Référence générique (pas de FK) : l'audit ne doit pas bloquer la suppression de la
    # ressource ; il conserve le type et l'identifiant sous forme de chaîne.
    resource_type = models.CharField(max_length=60, blank=True, default="")
    resource_id = models.CharField(max_length=64, blank=True, default="")

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "entrée d'audit"
        verbose_name_plural = "journal d'audit"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["developer", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.action} {self.resource_type}:{self.resource_id}"

    @classmethod
    def record(cls, *, action, actor=None, developer=None, resource_type="", resource_id="", request=None):
        """Point d'entrée unique d'écriture.

        Centraliser la création évite d'oublier de renseigner l'acteur ou l'IP selon le
        contexte d'appel. `request` est facultatif : on en extrait l'IP et le user-agent
        quand l'action provient d'une requête HTTP.
        Exemple : AccessLog.record(action="reveal_secret", actor=request.user,
                                   developer=project.developer, resource_type="Project",
                                   resource_id=str(project.id), request=request)
        """
        ip = None
        user_agent = ""
        if request is not None:
            user_agent = request.META.get("HTTP_USER_AGENT", "")[:1000]
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
            ip = (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR"))
            # On ne stocke que des IP valides : sinon on laisse le champ à NULL.
            if ip and len(ip) > 45:
                ip = None
        return cls.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            developer=developer,
            action=action,
            resource_type=resource_type or "",
            resource_id=str(resource_id or ""),
            ip_address=ip,
            user_agent=user_agent,
        )
