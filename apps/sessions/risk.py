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

Les poids ne sont PAS une vérité scientifique : ils sont centralisés ici pour être calibrés sur
des données réelles au Chapitre 3 (point à valider, comme les seuils RISK_THRESHOLDS).
"""

import math

from apps.events.catalog import CRITICAL_TYPES, category_for

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

# Poids utilisé pour une catégorie inconnue (type non répertorié) : on ne l'ignore pas.
DEFAULT_WEIGHT = 0.10


def compute_risk_score(events) -> float:
    """Renvoie un score de risque dans [0,1] pour une liste d'`Event`.

    `events` est n'importe quel itérable d'objets ayant `type` et `confidence_score`
    (typiquement `session.events.all()`). Exemple : 1 événement GAZE_AWAY_SUSTAINED
    (vision, confiance 0.92) → ~0.19 ; 5 événements critiques → > 0.6.
    """
    raw = 0.0
    for event in events:
        weight = CATEGORY_WEIGHTS.get(category_for(event.type), DEFAULT_WEIGHT)
        confidence = event.confidence_score
        # Sans confiance (événement booléen), on compte plein pot ; sinon on module.
        factor = 1.0 if confidence is None else CONFIDENCE_FLOOR + (1 - CONFIDENCE_FLOOR) * confidence
        if event.type in CRITICAL_TYPES:
            weight *= CRITICAL_MULTIPLIER
        raw += weight * factor

    score = 1 - math.exp(-raw)
    return round(score, 4)
