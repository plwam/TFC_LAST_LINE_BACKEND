"""Administration du journal SDK — consultation seule.

Les entrées arrivent par l'API machine (le SDK), jamais à la main : l'admin ne sert qu'à
inspecter/ filtrer en cas d'incident. On n'autorise ni création ni modification manuelle.
"""

from django.contrib import admin

from .models import SdkLog


@admin.register(SdkLog)
class SdkLogAdmin(admin.ModelAdmin):
    list_display = ["received_at", "project", "kind", "level", "sdk_version", "message"]
    list_filter = ["kind", "level", "project"]
    search_fields = ["message", "project__name", "sdk_version"]
    readonly_fields = [
        "id",
        "project",
        "session",
        "level",
        "kind",
        "message",
        "sdk_version",
        "context",
        "occurred_at",
        "received_at",
    ]
    date_hierarchy = "received_at"
    list_select_related = ["project", "session"]

    def has_add_permission(self, request):
        # Aucune saisie manuelle : les logs viennent du SDK.
        return False
