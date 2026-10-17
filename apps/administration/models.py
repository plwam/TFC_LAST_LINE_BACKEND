"""
Profil administrateur (01_BACKEND.md §3).

En pratique, un administrateur est un `User` avec `is_staff=True` (utilisable tel quel dans
le Django Admin natif). `Administrator` ne fait qu'ajouter une notion de rôle (superadmin /
moderator) SANS remplacer le système de permissions natif de Django : on « branche » ce profil
en cohérence avec `is_staff`, on ne le substitue pas.
"""

from django.conf import settings
from django.db import models


class Administrator(models.Model):
    class Role(models.TextChoices):
        SUPERADMIN = "superadmin", "superadmin"
        MODERATOR = "moderator", "moderator"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_profile",
    )
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        verbose_name = "administrateur"
        verbose_name_plural = "administrateurs"

    def __str__(self):
        return f"{self.user.email} ({self.role})"
