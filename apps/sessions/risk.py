"""
Calcul du score de risque d'une session — BF-16 (01_BACKEND.md §2, 06_FRONTEND_GUIDE.md §8.8).

Le score est un INDICATEUR D'AIDE À LA DÉCISION (0..1), jamais une preuve de fraude. Il est
dérivé du nombre, du type et de la confiance des événements, comme l'annonce l'interface.

Formule (volontairement simple et explicable) :
  1. chaque événement apporte un poids de base selon sa catégorie ;
  2. ce poids est modulé par la confiance du détecteur (un événement sans confiance — ex.
     FOCUS_LOST, purement binaire — compte à plein) ;
  3. un événement critique est renforcé (CRITICAL_MULTIPLIER) ;
  4. la somme « brute » est transformée par une saturation `1 - e^-x` → garantit un résultat
     borné dans [0,1] sans jamais l'atteindre brutalement (10 événements n'écrasent pas
     1 événement isolé, mais s'en rapprochent).

Trois correctifs de calibration (retour pédagogique) :
  - les événements de CONFORT de la candidature ne comptent pas dans le risque :
    {HANDS_VISIBLE_SUSTAINED, WARNING_ISSUED} sont exclus (le candidat qui montre ses mains
    ou reçoit un avertissement n'est pas un risque en soi) ;
  - la RÉPÉTITION du même type ne compte pas plein pot : la 1re occurrence compte plein
    poids, chaque occurrence suivante compte seulement REPEAT_FACTOR (0.3) — un candidat
    qui change 20 fois d'onglet ne peut pas saturer le score à lui tout seul ;
  - EXTENSION_HEARTBEAT_LOST compte pour un TOTAL fixe de 0.35 (HEARTBEAT_TOTAL_WEIGHT) :
    la perte de battement de cœur de l'extension est un fait binaire (l'extension n'a pas
    répondu), qui ne doit pas peser davantage parce que le backend l'a noté plusieurs fois.

Les poids ne sont PAS une vérité scientifique : ils sont centralisés ici pour être calibrés sur
des données réelles au Chapitre 3 (point à valider, comme les seuils RISK_THRESHOLDS).
"""

import math

from apps.events.catalog import CRITICAL_TYPES, category_for
from apps.events.models import Event

# Poids de base par catégorie : un signal « sécurité » pèse plus qu'un simple changement d'onglet.
CATEGORY_WEIGHTS = {
    "security": 0.35,
    "audio": 0.20,
    "vision": 0.15,
    "extension": 0.10,
    "browser": 0.05,
}
# Un événement critique compte 1,5× son poids de catégorie.
CRITICAL_MULTIPLIER = 1.5
# Plancher de confiance : un détecteur peu sûr ne peut pas réduire un événement à zéro.
CONFIDENCE_FLOOR = 0.5

# Types qui ne contribuent PAS au score (signaux de confort, pas de risque).
EXCLUDED_TYPES = frozenset(
    {Event.Type.HANDS_VISIBLE_SUSTAINED, Event.Type.WARNING_ISSUED}
)
# Occurrences suivantes d'un même type : elles comptent réduit (anti-chevauchement).
REPEAT_FACTOR = 0.3
# ECUM: poids TOTAL d'EXTENSION_HEARTBEAT_LOST, quelle que soit la répétition (fait binaire).
HEARTBEAT_TOTAL_WEIGHT = 0.35

# Poids utilisé pour une catégorie inconnue (type non répertorié) : on ne l'ignore pas.
DEFAULT_WEIGHT = 0.10


def compute_risk_score(events) -> float:
    """Renvoie un score de risque dans [0,1] pour une liste d'`Event`.

    `events` est n'importe quel itérable d'objets ayant `type` et `confidence_score`
    (typiquement `session.events.all()`). Exemple : 1 événement GAZE_AWAY_SUSTAINED
    (vision, confiance 0.92) → 0.144 brut → R ≈ 0.13.

    Ignorés : HANDS_VISIBLE_SUSTAINED, WARNING_ISSUED (confort) ; les répétitions d'un même
    type ne comptent qu'à 0.3 ; EXTENSION_HEARTBEAT_LOST plafonné à 0.35 au total.
    """
    raw = 0.0
    seen = {}
    heartbeat_counted = False
    for event in events:
        if event.type in EXCLUDED_TYPES:
            continue
        if event.type == Event.Type.EXTENSION_HEARTBEAT_LOST:
            # Fait binaire : l'extension n'a plus répondu. Poids total fixe.
            if heartbeat_counted:
                continue
            heartbeat_counted = True
            raw += HEARTBEAT_TOTAL_WEIGHT
            continue
        occurrences = seen.get(event.type, 0)
        seen[event.type] = occurrences + 1
        weight = CATEGORY_WEIGHTS.get(category_for(event.type), DEFAULT_WEIGHT)
        confidence = event.confidence_score
        # Sans confiance (événement booléen), on compte plein pot ; sinon on module.
        factor = 1.0 if confidence is None else CONFIDENCE_FLOOR + (1 - CONFIDENCE_FLOOR) * confidence
        if event.type in CRITICAL_TYPES:
            weight *= CRITICAL_MULTIPLIER
        if occurrences >= 1:
            weight *= REPEAT_FACTOR
        raw += weight * factor

    score = 1 - math.exp(-raw)
    return round(score, 4)
