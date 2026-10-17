"""
Profil métier « développeur » (01_BACKEND.md §3).

Un `Developer` est un rôle optionnel rattaché à un `User`. Toutes les données métier
(projets, sessions, événements) sont scopées sur le `Developer`, jamais sur le `User` :
l'isolation multi-tenant (01_BACKEND.md §12) s'appuie donc sur cette frontière.
"""

from django.conf import settings
from django.db import models


class Developer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        ACTIVE = "active", "active"
        SUSPENDED = "suspended", "suspended"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="developer_profile",
    )
    full_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "développeur"
        verbose_name_plural = "développeurs"

    def __str__(self):
        return f"{self.full_name} <{self.user.email}>"

    # --- Propriétés utilisées par l'interface (06_FRONTEND_GUIDE.md §7) ---
    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    @property
    def is_suspended(self) -> bool:
        return self.status == self.Status.SUSPENDED

    @property
    def can_write(self) -> bool:
        """Autorise les actions d'écriture : un compte `pending` peut préparer ses projets,
        un compte `suspended` est en lecture seule (refus côté serveur)."""
        return self.status != self.Status.SUSPENDED
