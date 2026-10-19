"""
Catalogue des événements — donnnées partagées entre modules (05_AGENT_GUIDELINES.md §5).

Ce module centralise deux informations qui découlent du contrat d'événement
(`00_PROJECT_OVERVIEW.md` §7.1) et sont utilisées à plusieurs endroits :
  - `EVENT_CATEGORIES` : catégorie d'affichage de chaque `EventType` (couleur du badge) ;
  - `CRITICAL_TYPES`   : types considérés comme critiques (bordure rouge + score de risque).

Pourquoi un module neutre plutôt que de laisser ces données dans le presenter (couche vue) :
le calcul du score de risque (app `sessions`) a besoin des mêmes catégories. Faire dépendre la
logique métier de la couche présentation créerait un couplage inversé. Ce catalogue ne dépend
d'aucune couche : tout le monde peut l'importer.
"""

from apps.events.models import Event

_T = Event.Type

# Catégorie d'affichage par type (06_FRONTEND_GUIDE.md §9.1, §9.2).
EVENT_CATEGORIES = {
    # Navigateur
    _T.FOCUS_LOST: "browser",
    _T.TAB_SWITCH: "browser",
    _T.COPY_PASTE_TEXT: "browser",
    _T.CLIPBOARD_IMAGE_PASTE: "browser",
    _T.PAGE_EXIT: "browser",
    _T.DOM_TAMPERING: "browser",
    _T.DEVTOOLS_OPEN: "browser",
    _T.FULLSCREEN_EXIT: "browser",
    _T.PRINT_ATTEMPT: "browser",
    _T.SUSPICIOUS_KEY_COMBO: "browser",
    _T.IDLE_TIMEOUT: "browser",
    _T.MULTI_MONITOR_DETECTED: "browser",
    # Sécurité
    _T.AUTOMATION_DETECTED: "security",
    _T.EXTENSION_HEARTBEAT_LOST: "security",
    _T.SIMULATED_EVENT_DETECTED: "security",
    # Vision
    _T.NO_FACE_DETECTED: "vision",
    _T.MULTIPLE_FACES: "vision",
    _T.FORBIDDEN_OBJECT_DETECTED: "vision",
    _T.VIRTUAL_DEVICE_DETECTED: "vision",
    _T.GAZE_AWAY_SUSTAINED: "vision",
    _T.REPEATED_HEAD_TURN: "vision",
    _T.HANDS_VISIBLE_SUSTAINED: "vision",
    # Audio
    _T.AUDIO_KEYWORD_MATCH: "audio",
    _T.MULTIPLE_VOICES: "audio",
    # Extension
    _T.TAB_CHANGE_EXT: "extension",
    _T.NAVIGATION_EXT: "extension",
    _T.SUSPICIOUS_ENVIRONMENT: "extension",
    # Retour candidat / interface
    _T.WARNING_ISSUED: "browser",
    _T.UI_TAMPERING: "security",
}

# Types critiques : marqués visuellement (bordure rouge) et pondérés davantage dans le score.
# Choix : tous les types de catégorie « security » + les signaux forts de surveillance.
# Liste volontairement explicite et centralisée — à ajuster après retour pédagogique.
CRITICAL_TYPES = frozenset(
    {
        _T.DOM_TAMPERING,
        _T.AUTOMATION_DETECTED,
        _T.EXTENSION_HEARTBEAT_LOST,
        _T.SIMULATED_EVENT_DETECTED,
        _T.FORBIDDEN_OBJECT_DETECTED,
        _T.VIRTUAL_DEVICE_DETECTED,
        _T.MULTIPLE_FACES,
        _T.AUDIO_KEYWORD_MATCH,
        _T.MULTIPLE_VOICES,
        _T.PAGE_EXIT,
    }
)


def category_for(event_type: str) -> str:
    """Catégorie d'un type, ou « security » par défaut pour un type inconnu (repli prudent)."""
    return EVENT_CATEGORIES.get(event_type, "security")
