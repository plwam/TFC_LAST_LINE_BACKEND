"""Administration des projets (01_BACKEND.md §8.8).

La clé secrète n'est JAMAIS exposée dans l'admin : `secret_key` est exclue du formulaire. Seuls
l'identifiant, la clé publique et les 4 derniers caractères sont visibles.

L'état d'un projet (actif / suspendu / désactivé) se pilote ici comme dans le dashboard
développeur : les actions en masse passent par le même `ProjectService` (jamais de logique
dupliquée) et écrivent une entrée d'audit.
"""

from django.contrib import admin

from apps.projects.services import ProjectService

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "developer", "site_url", "status", "is_archived", "created_at"]
    list_filter = ["status", "is_archived", "created_at"]
    search_fields = ["name", "developer__user__email", "public_key"]
    readonly_fields = ["id", "public_key", "secret_last4", "created_at", "updated_at"]
    list_select_related = ["developer", "developer__user"]
    actions = ["suspend_selected", "disable_selected", "reactivate_selected"]
    # Exclut la clé secrète : même un administrateur n'a pas à la voir en clair ici (elle est
    # chiffrée au repos et n'est révélée que par l'action dédiée, journalisée).
    exclude = ["secret_key"]

    @admin.action(description="Suspendre les projets sélectionnés")
    def suspend_selected(self, request, queryset):
        count = 0
        for project in queryset:
            ProjectService.suspend_project(project, actor=request.user, request=request)
            count += 1
        self.message_user(request, f"{count} projet(s) suspendu(s).")

    @admin.action(description="Désactiver les projets sélectionnés")
    def disable_selected(self, request, queryset):
        count = 0
        for project in queryset:
            ProjectService.disable_project(project, actor=request.user, request=request)
            count += 1
        self.message_user(request, f"{count} projet(s) désactivé(s).")

    @admin.action(description="Réactiver les projets sélectionnés")
    def reactivate_selected(self, request, queryset):
        count = 0
        for project in queryset:
            ProjectService.reactivate_project(project, actor=request.user, request=request)
            count += 1
        self.message_user(request, f"{count} projet(s) réactivé(s).")
