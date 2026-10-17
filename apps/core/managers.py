"""
Isolation multi-tenant (01_BACKEND.md §12).

Règle : aucune vue (template OU API) ne doit charger un objet par `pk` seul. On passe
toujours par ce gestionnaire scopé, qui renvoie 404 (via `get_object_or_404` côté vue)
pour une ressource appartenant à un autre développeur — on ne révèle jamais son existence.
"""

from django.db import models


class TenantScopedQuerySet(models.QuerySet):
    # Nom du chemin vers le développeur propriétaire. Redéfini par les modèles qui n'ont
    # pas de FK directe (ex. ExamSession → project.developer).
    TENANT_FIELD = "developer"

    def for_tenant(self, developer):
        """Restreint le queryset aux objets du développeur donné.

        Un `developer=None` (utilisateur sans profil) renvoie un queryset vide plutôt que
        d'exposer quoi que ce soit : un User sans profil Developer ne voit jamais de données.
        """
        if developer is None:
            return self.none()
        return self.filter(**{self.TENANT_FIELD: developer})


TenantScopedManager = models.Manager.from_queryset(TenantScopedQuerySet)
