"""Context processor du dashboard — exposé à TOUS les templates (06_FRONTEND_GUIDE.md §5.2)."""

from django.conf import settings


def dashboard_context(request):
    """Injecte le statut du développeur et les seuils de risque dans le contexte global.

    `getattr(..., None)` sur le profil : un visiteur anonyme ou un futur type d'utilisateur
    non-développeur reçoit `developer=None` au lieu de faire planter le rendu.
    """
    developer = getattr(getattr(request, "user", None), "developer_profile", None)
    return {
        "developer": developer,
        "developer_status": developer.status if developer else None,
        "risk_thresholds": settings.RISK_THRESHOLDS,
    }
