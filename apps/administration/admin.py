"""Administration — rôles (UC-11) et vue de métriques (UC-13), 01_BACKEND.md §8.8.

Aucun template admin custom n'est construit : on s'appuie sur le Django Admin natif. La seule
vue personnalisée est `/admin/metrics/` (UC-13), volontairement minimale.
"""

from django.contrib import admin
from django.db.models import Count
from django.shortcuts import render

from apps.developers.models import Developer
from apps.events.catalog import CRITICAL_TYPES
from apps.events.models import Event
from apps.projects.models import Project
from apps.sessions.models import ExamSession

from .models import Administrator


@admin.register(Administrator)
class AdministratorAdmin(admin.ModelAdmin):
    list_display = ["user", "role"]
    list_filter = ["role"]
    search_fields = ["user__email"]
    list_select_related = ["user"]


@admin.site.admin_view
def metrics_view(request):
    """Vue de métriques plateforme (UC-13). Accès réservé au staff (via `admin_view`).

    Affiche des compteurs agrégés — jamais de données personnelles étudiantes.
    """
    from django.conf import settings

    context = {
        **admin.site.each_context(request),
        "title": "Métriques",
        "metrics": {
            "developers_total": Developer.objects.count(),
            "developers_by_status": list(
                Developer.objects.values("status").annotate(n=Count("id")).order_by("status")
            ),
            "projects_total": Project.objects.count(),
            "projects_active": Project.objects.filter(is_archived=False).count(),
            "projects_archived": Project.objects.filter(is_archived=True).count(),
            "sessions_total": ExamSession.objects.count(),
            "sessions_active": ExamSession.objects.filter(status=ExamSession.Status.ACTIVE).count(),
            "sessions_high_risk": ExamSession.objects.filter(
                risk_score__gte=settings.RISK_THRESHOLDS["high"]
            ).count(),
            "events_total": Event.objects.count(),
            "events_critical": Event.objects.filter(type__in=CRITICAL_TYPES).count(),
        },
    }
    return render(request, "admin/metrics.html", context)
