"""Administration des projets (01_BACKEND.md §8.8).

La clé secrète n'est JAMAIS exposée dans l'admin : `secret_key` est exclue du formulaire. Seuls
l'identifiant, la clé publique et les 4 derniers caractères sont visibles.
"""

from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "developer", "site_url", "is_archived", "created_at"]
    list_filter = ["is_archived", "created_at"]
    search_fields = ["name", "developer__user__email", "public_key"]
    readonly_fields = ["id", "public_key", "secret_last4", "created_at", "updated_at"]
    list_select_related = ["developer", "developer__user"]
    # Exclut la clé secrète : même un administrateur n'a pas à la voir en clair ici (elle est
    # chiffrée au repos et n'est révélée que par l'action dédiée, journalisée).
    exclude = ["secret_key"]
