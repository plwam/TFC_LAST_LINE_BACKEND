"""
Filtres et tags de template du dashboard (06_FRONTEND_GUIDE.md §5.3).

Ces helpers traduisent les données brutes (score, durée en secondes, secret) en présentations
lisibles. Ils ne font aucun accès ORM : ils ne reçoivent que des valeurs déjà préparées par la
vue, ce qui évite les requêtes N+1 cachées dans les templates.
"""

from django import template
from django.conf import settings
from django.http import QueryDict
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def risk_level(score):
    """Classe un score [0,1] en "low" / "medium" / "high" selon settings.RISK_THRESHOLDS.

    Exemple : seuil medium=0.3, high=0.6 → 0.72 donne "high".
    Un score None renvoie "unknown" (badge « Calcul en cours »).
    """
    if score is None:
        return "unknown"
    if score >= settings.RISK_THRESHOLDS["high"]:
        return "high"
    if score >= settings.RISK_THRESHOLDS["medium"]:
        return "medium"
    return "low"


@register.filter
def duration(seconds):
    """Transforme une durée en secondes en libellé court.

    Exemple : 4320 → "1 h 12 min" ; 95 → "1 min 35 s" ; 42 → "42 s".
    """
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "—"
    if seconds < 0:
        return "—"
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {secs:02d} s"
    return f"{secs} s"


@register.filter
def offset(event_timestamp, session_start):
    """Décalage d'un événement depuis le début de session, formaté "T+hh:mm:ss".

    Exemple : un événement à 09:03:25 pour une session démarrée à 09:00:00 → "T+00:03:25".
    Utile pour recouper la chronologie avec le déroulé réel de l'examen.
    """
    if not event_timestamp or not session_start:
        return "—"
    delta = event_timestamp - session_start
    total = int(delta.total_seconds())
    if total < 0:
        return "—"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"T+{hours:02d}:{minutes:02d}:{secs:02d}"


@register.filter
def mask_secret(value):
    """Masque une clé secrète en ne laissant voir que les 4 derniers caractères.

    Exemple : "sk_live_abc…1234" → "sk_live_••••1234". Utilisé uniquement pour l'affichage ;
    le HTML initial ne contient jamais la valeur complète.
    """
    if not value:
        return "sk_live_••••????"
    return f"sk_live_••••{str(value)[-4:]}"


@register.filter
def to_json(value):
    """Sérialise une valeur (ex. `Event.metadata`) en JSON lisible.

    Le résultat est une chaîne : Django l'auto-échappe à l'affichage, donc des métadonnées
    contenant `<script>` s'affichent littéralement sans jamais être exécutées (06 §11).
    """
    import json

    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)


@register.simple_tag
def tz_label():
    """Affiche le libellé de fuseau ("UTC") à côté des horodatages (06 §17, point 3)."""
    return format_html('<span class="text-slate-500">UTC</span>')


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """Reconstruit la query string courante en remplaçant/ajoutant des paramètres.

    Utilisé par la pagination pour CONSERVER les filtres GET actifs (06 §4.2).
    Exemple : URL ?q=univ&page=2 → {% querystring page=1 %} donne "q=univ&page=1".
    """
    request = context.get("request")
    params = request.GET.copy() if request else QueryDict(mutable=True)
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
