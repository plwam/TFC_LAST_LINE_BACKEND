"""Administration du journal d'audit — lecture seule (01_BACKEND.md §8.8, BNF-33).

Un journal d'audit ne se modifie jamais : on n'expose que la consultation (filtres par acteur,
action et date).
"""

from django.contrib import admin

from .models import AccessLog


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "actor", "developer", "resource_type", "resource_id"]
    list_filter = ["action", "created_at", "resource_type"]
    search_fields = ["actor__email", "developer__user__email", "resource_id"]
    date_hierarchy = "created_at"
    # Tous les champs sont en lecture seule, et l'ajout est impossible : le journal est écrit
    # uniquement par le code (`AccessLog.record`, middleware), jamais à la main.
    readonly_fields = [f.name for f in AccessLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
