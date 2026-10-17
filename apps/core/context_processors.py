"""Context processors transverses (apps.core).

Exposé à TOUS les templates (dashboard, surcharges allauth, landing publique) via
TEMPLATES.OPTIONS.context_processors — le logo doit être identique partout.
"""

from apps.core.models import SiteBranding


def site_branding(request):
    """Injecte l'identité visuelle (`site_branding`) dans le contexte global.

    Renvoie TOUJOURS un objet (valeurs par défaut si aucun n'a été enregistré), afin que
    `{{ site_branding.site_name }}` soit toujours défini. La lecture seule ne crée pas de ligne.

    Défensif par conception : ce processor tourne aussi pour les pages d'erreur (404/500), y
    compris quand la base est injoignable — on ne veut pas qu'un souci d'identité visuelle
    empêche l'affichage d'une page d'erreur.
    """
    try:
        return {"site_branding": SiteBranding.get_solo()}
    except Exception:  # noqa: BLE001 — page d'erreur : on retombe sur les valeurs par défaut.
        return {"site_branding": SiteBranding()}
