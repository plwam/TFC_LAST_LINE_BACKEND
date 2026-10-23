"""
Traduction des événements techniques en phrases lisibles — `presenters.py` (06 §9).

Principe : la base stocke des `EventType` techniques ; l'examen est lu par des enseignants.
Un presenter central convertit `(type, metadata)` en `(libellé, catégorie, phrase, critique)`.

Règles non négociables :
1. On ne renvoie QUE du texte brut — jamais `mark_safe`/`|safe` : les `metadata` proviennent
   du navigateur de l'étudiant et ne sont pas dignes de confiance (risque XSS). L'auto-échap-
   pement de Django reste la seule protection à l'affichage.
2. Défensif : une clé de `metadata` absente ou mal typée ne doit JAMAIS provoquer d'exception ;
   on retombe sur une phrase de repli sans chiffres (06 §9).
3. Les phrases sont du français ; les nombres suivent la convention française (« 3,4 s »,
   confiance en pourcentage entier « 87 % »).

Exemple complet :
    present_event(Event(type="GAZE_AWAY_SUSTAINED",
                        metadata={"durationMs": 3400, "gaze": {"yawDeg": 32, "pitchDeg": 5}}))
    → EventPresentation(label="Regard détourné", category="vision",
                        sentence="Regard détourné pendant 3,4 s (angle horizontal 32°, "
                                 "vertical 5°).", critical=False)
"""

import json
from dataclasses import dataclass

from django.utils import timezone

from apps.events.catalog import CRITICAL_TYPES
from apps.events.models import Event


@dataclass(frozen=True)
class EventPresentation:
    """Vue prête à afficher d'un événement. Champs texte uniquement (jamais de HTML)."""

    label: str
    category: str  # browser | vision | audio | extension | security
    sentence: str
    critical: bool


# Libellés de catégorie (le badge coloré lui-même est choisi dans `badge_event.html`).
CATEGORY_LABELS = {
    "browser": "Navigateur",
    "vision": "Vision",
    "audio": "Audio",
    "extension": "Extension",
    "security": "Sécurité",
}

# Types considérés comme CRITIQUES → bordure rouge dans la chronologie (§8.8).
# La liste vit désormais dans `apps/events/catalog.py` (partagée avec le score de risque) et est
# ré-exportée ici pour ne pas casser les imports existants (`dashboard.views`).


# ---------------------------------------------------------------------------
# Helpers de formatage défensifs (jamais d'exception sur donnée absente/malformée)
# ---------------------------------------------------------------------------
def _md(metadata) -> dict:
    """Normalise `metadata` en dict ; une valeur non-dict devient un dict vide."""
    return metadata if isinstance(metadata, dict) else {}


def _raw(metadata, key):
    """Lit une clé de premier niveau sans jamais lever."""
    return _md(metadata).get(key)


def _number(value, decimals=1):
    """Formate un nombre en français (« 3,4 »). Renvoie None si non numérique."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return f"{float(value):.{decimals}f}".replace(".", ",")
    except (TypeError, ValueError):
        return None


def _seconds_from_ms(metadata, key):
    """Convertit une durée en millisecondes en secondes lisibles.

    Exemple : {"durationMs": 3400} → "3,4". Renvoie None si la clé manque ou n'est pas
    numérique (une valeur « durationMs »: "abc" ne doit pas faire planter l'affichage).
    """
    raw = _raw(metadata, key)
    if raw is None:
        return None
    try:
        return _number(float(raw) / 1000.0)
    except (TypeError, ValueError):
        return None


def _int(value):
    """Renvoie un entier prudent, ou None."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _conf(value):
    """Formate une confiance [0,1] en pourcentage entier (« 87 »). Renvoie None sinon."""
    n = _number(value, decimals=2)
    if n is None:
        return None
    try:
        return str(int(round(float(value) * 100)))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Phrases de repli (utilisées dès qu'un chiffre attendu manque)
# ---------------------------------------------------------------------------
def _fixed(sentence):
    """Génère une fonction de phrase constante (types sans métadonnées numériques)."""
    return lambda metadata: sentence


def _suspicious_combo(metadata):
    combo = _raw(metadata, "combo")
    return f"Raccourci clavier suspect : {combo}." if combo else "Raccourci clavier suspect."


def _idle(metadata):
    seconds = _seconds_from_ms(metadata, "idleMs")
    return (
        f"Aucune activité pendant {seconds} s."
        if seconds
        else "Aucune activité détectée pendant une période prolongée."
    )


def _multiple_faces(metadata):
    count = _int(_raw(metadata, "count"))
    if count is None:
        return "Plusieurs personnes détectées."
    plural = count > 1
    return f"{count} personne{'s' if plural else ''} détectée{'s' if plural else ''}."


# Traduction française des étiquettes COCO-SSD connues (02c §6.2) : la phrase de repli affiche
# un nom parlant plutôt que « objet interdit ».
_OBJECT_FR = {
    "cell phone": "Téléphone",
    "phone": "Téléphone",
    "headphones": "Écouteurs",
    "book": "Livre",
    "laptop": "Ordinateur portable",
    "remote": "Télécommande",
    "tv": "Écran",
    "keyboard": "Clavier",
    "mouse": "Souris",
}


def _objects_detected(metadata):
    objects = _raw(metadata, "objects")
    if not isinstance(objects, list):
        return "Objets détectés dans l'image."
    parts = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        if not label:
            continue
        name = _OBJECT_FR.get(label, label)
        conf = _conf(item.get("confidence"))
        parts.append(f"{name} ({conf} %)" if conf is not None else name)
    if not parts:
        return "Objets détectés dans l'image."
    return f"Objets détectés : {', '.join(parts)}."


def _forbidden_object(metadata):
    label = _raw(metadata, "label")
    conf = _conf(_raw(metadata, "confidence"))
    if not label:
        return "Objet non identifié détecté."
    name = _OBJECT_FR.get(label, label)
    if conf is None:
        return f"{name} détecté."
    return f"{name} détecté (confiance {conf} %)."


def _gaze(metadata):
    seconds = _seconds_from_ms(metadata, "durationMs")
    gaze = _md(_raw(metadata, "gaze"))
    yaw = _number(gaze.get("yawDeg"), decimals=0)
    pitch = _number(gaze.get("pitchDeg"), decimals=0)
    if seconds and yaw is not None and pitch is not None:
        return f"Regard détourné pendant {seconds} s (angle horizontal {yaw}°, vertical {pitch}°)."
    if seconds:
        return f"Regard détourné pendant {seconds} s."
    return "Regard détourné détecté."


def _head_turn(metadata):
    occurrences = _int(_raw(metadata, "occurrences"))
    window = _seconds_from_ms(metadata, "windowMs")
    if occurrences is not None and window:
        return f"Tête tournée {occurrences} fois en {window} s."
    return "Mouvements de tête répétés détectés."


def _hands(metadata):
    seconds = _seconds_from_ms(metadata, "durationMs")
    return (
        f"Mains visibles dans le champ pendant {seconds} s."
        if seconds
        else "Mains visibles dans le champ."
    )


def _audio_keyword(metadata):
    keyword = _raw(metadata, "keyword")
    confirmed = _int(_raw(metadata, "confirmedOccurrences"))
    if keyword and confirmed is not None:
        return f"Mot-clé d'examen entendu : « {keyword} » (confirmé sur {confirmed} segments)."
    if keyword:
        return f"Mot-clé d'examen entendu : « {keyword} »."
    return "Mot-clé d'examen entendu."


def _voices(metadata):
    count = _int(_raw(metadata, "voiceCount"))
    return (
        f"{count} voix distinctes détectées." if count is not None else "Plusieurs voix détectées."
    )


def _navigation_ext(metadata):
    # Minimisation (06 §9, §17 point 6) : on n'affiche QUE le nom de domaine, jamais l'URL
    # complète — le chemin peut contenir des informations personnelles.
    hostname = _raw(metadata, "hostname")
    return f"Navigation vers {hostname}." if hostname else "Navigation détectée par l'extension."


def _suspicious_env(metadata):
    resolution = _raw(metadata, "abnormalResolution")
    displays = _int(_raw(metadata, "displayCount"))
    parts = []
    if resolution:
        parts.append(f"résolution anormale : {resolution}")
    if displays is not None:
        parts.append(f"écrans : {displays}")
    if parts:
        return "Environnement atypique (" + ", ".join(parts) + ")."
    return "Environnement atypique détecté."


def _warning_issued(metadata):
    severity = _raw(metadata, "severity")
    source = _raw(metadata, "sourceEvent")
    count = _int(_raw(metadata, "occurrenceCount"))
    parts = []
    if severity:
        parts.append(f"gravité {severity}")
    if count is not None:
        parts.append(f"occurrence {count}")
    if source:
        parts.append(f"déclencheur {source}")
    if parts:
        return "Avertissement au candidat (" + ", ".join(parts) + ")."
    return "Avertissement au candidat."


def _ui_tampering(metadata):
    reason = _raw(metadata, "reason")
    labels = {
        "surveillance element removed": "élément de surveillance retiré",
        "surveillance element hidden": "élément de surveillance masqué",
    }
    if reason in labels:
        return f"Interface de surveillance altérée : {labels[reason]}."
    return "Interface de surveillance altérée."


# ---------------------------------------------------------------------------
# Table de présentation des 29 types (06 §9.2)
# ---------------------------------------------------------------------------
EVENT_PRESENTATION = {
    # --- Navigateur ---
    Event.Type.FOCUS_LOST: ("Perte de focus", "browser", _fixed("La fenêtre d'examen a perdu le focus.")),
    Event.Type.TAB_SWITCH: ("Changement d'onglet", "browser", _fixed("Changement d'onglet ou fenêtre masquée.")),
    Event.Type.COPY_PASTE_TEXT: ("Copier-coller", "browser", _fixed("Copier ou coller de texte détecté.")),
    Event.Type.CLIPBOARD_IMAGE_PASTE: ("Image collée", "browser", _fixed("Une image a été collée depuis le presse-papiers.")),
    Event.Type.PAGE_EXIT: ("Sortie de page", "browser", _fixed("Tentative de quitter la page d'examen.")),
    Event.Type.DOM_TAMPERING: ("Page modifiée", "browser", _fixed("Modification suspecte de la page d'examen.")),
    Event.Type.DEVTOOLS_OPEN: ("Outils développeur", "browser", _fixed("Outils de développement probablement ouverts (détection indicative).")),
    Event.Type.FULLSCREEN_EXIT: ("Sortie plein écran", "browser", _fixed("Sortie du mode plein écran.")),
    Event.Type.PRINT_ATTEMPT: ("Impression", "browser", _fixed("Tentative d'impression.")),
    Event.Type.SUSPICIOUS_KEY_COMBO: ("Raccourci suspect", "browser", _suspicious_combo),
    Event.Type.IDLE_TIMEOUT: ("Inactivité", "browser", _idle),
    Event.Type.MULTI_MONITOR_DETECTED: ("Plusieurs écrans", "browser", _fixed("Plusieurs écrans détectés.")),

    # --- Sécurité ---
    Event.Type.AUTOMATION_DETECTED: ("Automatisation", "security", _fixed("Navigateur piloté par un script d'automatisation.")),
    Event.Type.EXTENSION_HEARTBEAT_LOST: ("Extension injoignable", "security", _fixed("L'extension ne répond plus : la poursuite de l'examen a été bloquée.")),
    Event.Type.SIMULATED_EVENT_DETECTED: ("Événement simulé", "security", _fixed("Tentative d'injection d'événements simulés.")),

    # --- Vision ---
    Event.Type.NO_FACE_DETECTED: ("Aucun visage", "vision", _fixed("Aucun visage détecté dans l'image.")),
    Event.Type.MULTIPLE_FACES: ("Plusieurs visages", "vision", _multiple_faces),
    Event.Type.OBJECT_DETECTED: ("Objets détectés", "vision", _objects_detected),
    Event.Type.FORBIDDEN_OBJECT_DETECTED: ("Objet interdit", "vision", _forbidden_object),
    Event.Type.VIRTUAL_DEVICE_DETECTED: ("Périphérique virtuel", "vision", _fixed("Caméra ou micro virtuel détecté (indicatif, liste de noms connus).")),
    Event.Type.GAZE_AWAY_SUSTAINED: ("Regard détourné", "vision", _gaze),
    Event.Type.REPEATED_HEAD_TURN: ("Tête tournée", "vision", _head_turn),
    Event.Type.HANDS_VISIBLE_SUSTAINED: ("Mains visibles", "vision", _hands),

    # --- Audio ---
    Event.Type.AUDIO_KEYWORD_MATCH: ("Mot-clé audio", "audio", _audio_keyword),
    Event.Type.MULTIPLE_VOICES: ("Plusieurs voix", "audio", _voices),

    # --- Extension ---
    Event.Type.TAB_CHANGE_EXT: ("Onglet (extension)", "extension", _fixed("Changement d'onglet détecté par l'extension.")),
    Event.Type.NAVIGATION_EXT: ("Navigation (extension)", "extension", _navigation_ext),
    Event.Type.SUSPICIOUS_ENVIRONMENT: ("Environnement atypique", "extension", _suspicious_env),

    # --- Retour candidat / interface ---
    Event.Type.WARNING_ISSUED: ("Avertissement candidat", "browser", _warning_issued),
    Event.Type.UI_TAMPERING: ("Surveillance masquée", "security", _ui_tampering),
}


def label_for_type(event_type: str) -> str:
    """Libellé lisible d'un type brut, sans instance d'`Event` (utile pour les décomptes).

    Exemple : "MULTIPLE_FACES" → "Plusieurs visages". Un type inconnu est retourné tel quel.
    """
    spec = EVENT_PRESENTATION.get(event_type)
    return spec[0] if spec else event_type


def present_event(event) -> EventPresentation:
    """Convertit un `Event` en `EventPresentation` (06 §9).

    Défensif : un type inconnu (ajouté au SDK mais pas encore ici) affiche son nom brut plutôt
    que de planter — la chronologie reste consultable même en cas de désynchronisation de
    contrat entre modules (05_AGENT_GUIDELINES.md §5).
    """
    spec = EVENT_PRESENTATION.get(event.type)
    if spec is None:
        return EventPresentation(
            label=event.type,
            category="security",
            sentence="Événement non répertorié.",
            critical=False,
        )
    label, category, sentence_fn = spec
    return EventPresentation(
        label=label,
        category=category,
        sentence=sentence_fn(event.metadata or {}),
        critical=event.type in CRITICAL_TYPES,
    )


# ---------------------------------------------------------------------------
# Journal SDK (onglet « Journal SDK ») — 06 §8.6
# ---------------------------------------------------------------------------
# Libellés lisibles. Comme pour les événements, on ne renvoie QUE du texte brut (les `context`
# proviennent du SDK et ne sont jamais injectés avec `|safe`).

SDK_STATE_LABELS = {
    "online": "En ligne",
    "degraded": "Dégradé",
    "offline": "Hors ligne",
}

LOG_LEVEL_LABELS = {
    "debug": "Débogage",
    "info": "Information",
    "warning": "Avertissement",
    "error": "Erreur",
}

LOG_KIND_LABELS = {
    "heartbeat": "Signal de vie",
    "log": "Journal",
}


def _fmt_datetime(value) -> str:
    """Formate un horodatage en UTC (« 15/10/2024 12:30:00 ») ; chaîne vide si absent."""
    if not value:
        return ""
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M:%S")


def sdk_status_row(status) -> dict:
    """Convertit un `apps.sdklogs.status.SdkStatus` en dict prêt à afficher / sérialiser."""
    return {
        "state": status.state,
        "label": SDK_STATE_LABELS.get(status.state, status.state),
        "last_heartbeat_display": _fmt_datetime(status.last_heartbeat),
        "last_seen_display": _fmt_datetime(status.last_seen),
        "recent_errors": status.recent_errors,
    }


def log_row(log) -> dict:
    """Vue affichable/sérialisable d'une entrée du journal SDK.

    Utilisée à la fois par le template (rendu serveur) et par le flux JSON (temps réel), pour
    garantir que les deux présentent EXACTEMENT les mêmes champs.
    """
    context = log.context if isinstance(log.context, dict) else {}
    session = log.session
    return {
        "id": str(log.id),
        "level": log.level,
        "level_label": LOG_LEVEL_LABELS.get(log.level, log.level),
        "kind": log.kind,
        "kind_label": LOG_KIND_LABELS.get(log.kind, log.kind),
        "message": log.message or "",
        "sdk_version": log.sdk_version or "",
        "has_context": bool(context),
        "context_json": (
            json.dumps(context, ensure_ascii=False, indent=2, default=str) if context else ""
        ),
        "session_label": f"{session.exam_id} / {session.student_id}" if session else "",
        "received_at": log.received_at.isoformat() if log.received_at else "",
        "received_display": _fmt_datetime(log.received_at),
    }
