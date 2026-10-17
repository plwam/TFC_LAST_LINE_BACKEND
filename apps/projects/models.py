"""
Modèle `Project` (01_BACKEND.md §5.1).

Un projet est l'unité d'isolation multi-tenant : il porte la `site_url` qui alimente la liste
blanche de l'extension (03_EXTENSION.md §5) et les deux clés utilisées par le SDK.

Note sur la suppression (06_FRONTEND_GUIDE.md §17, point 1) : la spec prévoit à la fois
`on_delete=CASCADE` depuis Project et l'immuabilité des événements (REVOKE DELETE). Ces deux
règles sont incompatibles pour une suppression physique. On retient la proposition par défaut :
la « suppression » est un **archivage** (`is_archived=True`, clés désactivées, données
conservées) ; une purge définitive relèvera d'une tâche de maintenance privilégiée distincte.
Ce point reste à valider explicitement (signalé).
"""

import uuid

from django.db import models

from apps.core.fields import EncryptedTextField
from apps.core.managers import TenantScopedManager


class Project(models.Model):
    class Status(models.TextChoices):
        # Cycle de vie d'un projet, distinct de l'archivage : un projet `suspended`/`disabled`
        # garde ses données et sa place dans le dashboard, mais ses clés ne valident plus rien.
        ACTIVE = "active", "active"
        SUSPENDED = "suspended", "suspended"
        DISABLED = "disabled", "disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    developer = models.ForeignKey(
        "developers.Developer",
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    site_url = models.URLField(max_length=500)

    # Clé publique : non confidentielle, affichée en clair, intégrée à la page d'examen (SDK).
    public_key = models.CharField(max_length=64, unique=True, db_index=True)
    # Clé secrète : chiffrée au repos via EncryptedTextField (01_BACKEND.md §12). Jamais
    # exposée dans le HTML initial ; transite uniquement via la réponse du reveal.
    secret_key = EncryptedTextField()
    # Seuls les 4 derniers caractères sont conservés en clair pour l'affichage masqué
    # « sk_live_••••1234 » sans avoir à déchiffrer le secret à chaque rendu de page.
    secret_last4 = models.CharField(max_length=4, blank=True, default="")

    # Cycle de vie du projet (actif / suspendu / désactivé). Distinct de l'archivage :
    # suspendre ou désactiver coupe les clés HMAC sans supprimer le projet, et est réversible.
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )

    # Archivage (voir note de module) — remplace une suppression physique destructrice.
    is_archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Gestionnaire scopé : les vues appellent `Project.objects.for_tenant(developer)` pour
    # garantir l'isolation (jamais un `get(pk=...)` nu).
    objects = TenantScopedManager()

    class Meta:
        verbose_name = "projet"
        verbose_name_plural = "projets"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def masked_secret(self) -> str:
        """Représentation masquée affichable sans jamais révéler le secret.

        Exemple : "sk_live_••••a1b2".
        """
        return f"sk_live_••••{self.secret_last4 or '????'}"

    # --- Cycle de vie : propriétés utilisées par l'interface et l'authentification machine ---
    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    @property
    def is_suspended(self) -> bool:
        return self.status == self.Status.SUSPENDED

    @property
    def is_disabled(self) -> bool:
        return self.status == self.Status.DISABLED

    @property
    def accepts_traffic(self) -> bool:
        """Vrai si les clés HMAC du projet doivent être acceptées (actif ET non archivé)."""
        return self.is_active and not self.is_archived
