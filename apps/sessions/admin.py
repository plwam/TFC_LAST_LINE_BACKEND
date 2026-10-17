"""Administration des sessions d'examen (UC-6, UC-11..13).

Consultation surtout : les sessions sont créées par le SDK (API machine), pas à la main.
"""

from django.contrib import admin

from .models import ExamSession


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ["exam_id", "student_id", "project", "status", "risk_score", "started_at"]
    list_filter = ["status", "started_at"]
    search_fields = ["exam_id", "student_id", "project__name"]
    readonly_fields = ["id", "risk_score", "created_at", "updated_at"]
    date_hierarchy = "started_at"
    list_select_related = ["project"]
