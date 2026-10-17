"""Administration des événements — LECTURE SEULE stricte (immuabilité, BNF-33).

Aucun ajout, aucune modification, aucune suppression : un événement est une preuve. Sa création
passe exclusivement par l'API machine. (En production MySQL, le privilège `DELETE` est en plus
révoqué sur la table `events`.)
"""

from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["occurred_at", "type", "source", "session", "confidence_score"]
    list_filter = ["type", "source", "occurred_at"]
    search_fields = ["session__exam_id", "session__student_id", "event_id"]
    date_hierarchy = "occurred_at"
    list_select_related = ["session"]
    readonly_fields = [f.name for f in Event._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
