"""Administration des développeurs (UC-12, 01_BACKEND.md §8.8).

Actions en masse « Valider » / « Suspendre » : ce sont les deux leviers de modération du cycle
de vie d'un compte. Chaque action écrit une entrée d'audit (qui a validé/suspendu qui, quand).
"""

from django.contrib import admin

from apps.audit.models import AccessLog

from .models import Developer


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    # Conformes à 01_BACKEND.md §8.8. `email` est une méthode calculée (le champ vit sur `User`).
    list_display = ["email", "full_name", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["user__email", "full_name"]
    readonly_fields = ["created_at"]
    actions = ["approve_selected", "suspend_selected"]
    list_select_related = ["user"]

    @admin.display(description="Email", ordering="user__email")
    def email(self, obj):
        return obj.user.email

    @admin.action(description="Valider les comptes sélectionnés")
    def approve_selected(self, request, queryset):
        # On journalise APRÈS la mise à jour, en une passe par développeur (l'audit garde le
        # détail de qui a été validé, pas seulement le nombre).
        for developer in queryset:
            developer.status = Developer.Status.ACTIVE
            developer.save(update_fields=["status"])
            AccessLog.record(
                action=AccessLog.Action.VALIDATE_DEVELOPER,
                actor=request.user,
                developer=developer,
                resource_type="Developer",
                resource_id=str(developer.pk),
                request=request,
            )
        self.message_user(request, f"{queryset.count()} développeur(s) validé(s).")

    @admin.action(description="Suspendre les comptes sélectionnés")
    def suspend_selected(self, request, queryset):
        count = 0
        for developer in queryset:
            developer.status = Developer.Status.SUSPENDED
            developer.save(update_fields=["status"])
            AccessLog.record(
                action=AccessLog.Action.SUSPEND_DEVELOPER,
                actor=request.user,
                developer=developer,
                resource_type="Developer",
                resource_id=str(developer.pk),
                request=request,
            )
            count += 1
        self.message_user(request, f"{count} développeur(s) suspendu(s).")
