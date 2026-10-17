"""
Couche de service partagée (01_BACKEND.md §7).

Règle non négociable : la logique métier (créer un projet, régénérer une clé) vit ICI, jamais
dans les vues. Les vues templates (dashboard) et les vues DRF (API JWT, étape 2) appellent les
MÊMES méthodes de service — un futur changement de règle (ex. quota de projets par développeur)
se corrige à un seul endroit.
"""

import secrets

from django.db import transaction

from apps.audit.models import AccessLog

from .models import Project

# Préfixes des clés, cohérents avec la charte d'affichage du dashboard (« pk_live_… » /
# « sk_live_… »). Ils n'ont aucune valeur cryptographique : purement lisibles.
PUBLIC_KEY_PREFIX = "pk_live_"
SECRET_KEY_PREFIX = "sk_live_"


class KeyService:
    """Génération et cycle de vie des clés d'un projet."""

    @staticmethod
    def _new_public_key() -> str:
        """Clé publique unique (jamais secrète). `token_hex(24)` = 48 caractères hex."""

        return f"{PUBLIC_KEY_PREFIX}{secrets.token_hex(24)}"

    @staticmethod
    def _new_secret_key() -> str:
        """Clé secrète à haute entropie (utilisée pour signer les jetons HMAC côté serveur)."""
        return f"{SECRET_KEY_PREFIX}{secrets.token_hex(32)}"

    @classmethod
    def generate_keys(cls, project: Project) -> tuple[str, str]:
        """Génère et enregistre un couple de clés NEUF sur le projet (BF-05).

        Renvoie `(public_key, secret_key)` en clair. L'unicité de la clé publique est garantie
        par une boucle de ré-essai — une collision sur 48 caractères hexadécimaux est
        exceptionnellement improbable, mais on ne parie pas sur l'improbable pour une contrainte
        de base.
        """
        public_key = cls._new_public_key()
        while Project.objects.filter(public_key=public_key).exists():
            public_key = cls._new_public_key()

        secret_key = cls._new_secret_key()
        project.public_key = public_key
        project.secret_key = secret_key  # chiffré automatiquement à l'écriture (EncryptedTextField)
        project.secret_last4 = secret_key[-4:]
        project.save(update_fields=["public_key", "secret_key", "secret_last4", "updated_at"])
        return public_key, secret_key


class ProjectService:
    """Opérations métier sur les projets, partagées par le dashboard et l'API."""

    @staticmethod
    @transaction.atomic
    def create_project(developer, name: str, description: str, site_url: str) -> Project:
        """Crée un projet et lui génère immédiatement ses clés (BF-05, systématique).

        Transaction atomique : si la génération de clés échoue, on ne laisse pas un projet
        sans clés derrière soi. Journalise l'action dans AccessLog (BNF-33).
        Exemple : create_project(dev, "Univ-A", "Examens de maths", "https://examens.univ-a.edu")
        """
        project = Project.objects.create(
            developer=developer,
            name=name,
            description=description,
            site_url=site_url,
            # Valeurs provisoires : KeyService les remplace juste après.
            public_key=f"pending-{secrets.token_hex(8)}",
            secret_key="pending",
        )
        KeyService.generate_keys(project)
        AccessLog.record(
            action=AccessLog.Action.CREATE_PROJECT,
            developer=developer,
            actor=getattr(developer, "user", None),
            resource_type="Project",
            resource_id=str(project.id),
        )
        return project

    @staticmethod
    @transaction.atomic
    def update_project(project: Project, **fields) -> Project:
        """Met à jour les champs modifiables (nom, description, site_url)."""
        allowed = {"name", "description", "site_url"}
        for key, value in fields.items():
            if key in allowed:
                setattr(project, key, value)
        project.save()
        AccessLog.record(
            action=AccessLog.Action.UPDATE_PROJECT,
            developer=project.developer,
            actor=getattr(project.developer, "user", None),
            resource_type="Project",
            resource_id=str(project.id),
        )
        return project

    @staticmethod
    @transaction.atomic
    def archive_project(project: Project) -> Project:
        """Archive un projet (voir note de modèle : remplace une suppression destructrice).

        Les clés restent physiquement stockées mais le projet est marqué `is_archived` : les
        sessions HMAC et l'inscription à `/public/registered-hosts/` devront refuser un projet
        archivé (implémenté à l'étape 2, côté machine_api/public).
        """
        project.is_archived = True
        project.save(update_fields=["is_archived", "updated_at"])
        AccessLog.record(
            action=AccessLog.Action.DELETE_PROJECT,
            developer=project.developer,
            actor=getattr(project.developer, "user", None),
            resource_type="Project",
            resource_id=str(project.id),
        )
        return project

    @classmethod
    @transaction.atomic
    def suspend_project(cls, project: Project, *, actor=None, request=None) -> Project:
        """Suspend un projet : ses clés HMAC cessent d'être acceptées, réversible (UC-2/UC-12).

        Utilisé par le développeur (mesure sur son propre projet) comme par l'administration.
        Audit dédié (`suspend_project`) pour distinguer la suspension des autres changements.
        """
        return cls._set_status(
            project, Project.Status.SUSPENDED, AccessLog.Action.SUSPEND_PROJECT, actor, request
        )

    @classmethod
    @transaction.atomic
    def disable_project(cls, project: Project, *, actor=None, request=None) -> Project:
        """Désactive un projet (mis au repos) : clés refusées, réversible via `reactivate`."""
        return cls._set_status(
            project, Project.Status.DISABLED, AccessLog.Action.DISABLE_PROJECT, actor, request
        )

    @classmethod
    @transaction.atomic
    def reactivate_project(cls, project: Project, *, actor=None, request=None) -> Project:
        """Réactive un projet suspendu/désactivé : ses clés redeviennent valides."""
        return cls._set_status(
            project, Project.Status.ACTIVE, AccessLog.Action.REACTIVATE_PROJECT, actor, request
        )

    @staticmethod
    def _set_status(project, status, action, actor, request) -> Project:
        """Applique un nouvel état et journalise l'action (point d'écriture unique)."""
        project.status = status
        project.save(update_fields=["status", "updated_at"])
        AccessLog.record(
            action=action,
            actor=actor,
            developer=project.developer,
            resource_type="Project",
            resource_id=str(project.id),
            request=request,
        )
        return project

    @staticmethod
    @transaction.atomic
    def regenerate_secret_key(project: Project, *, actor=None, request=None) -> str:
        """Régénère la clé secrète : l'ancienne est IMMÉDIATEMENT invalidée (UC-3).

        `KeyService.generate_keys` écrase la clé secrète en base ; toute session signée avec
        l'ancienne clé cessera d'être acceptée. Journalise l'opération (action sensible).
        Renvoie la nouvelle clé secrète (affichée une seule fois via « Révéler »).
        """
        _, secret_key = KeyService.generate_keys(project)
        AccessLog.record(
            action=AccessLog.Action.REGENERATE_SECRET,
            actor=actor,
            developer=project.developer,
            resource_type="Project",
            resource_id=str(project.id),
            request=request,
        )
        return secret_key
