"""
Primitives cryptographiques HMAC — API machine (SDK / LMS), 01_BACKEND.md §9, §12.

Modèle Zero Trust : aucune notion d'utilisateur connecté. Le serveur du développeur signe
un jeton de session avec sa `secret_key` ; ExamSDK revérifie la signature en temps constant.
"""

import hashlib
import hmac
import time


def sign_message(secret_key: str, message: str) -> str:
    """Calcule la signature HMAC-SHA256 (hexadécimal) d'un message.

    Utilisée côté serveur du développeur (exemples de l'onglet « Intégration ») et rejouée
    côté serveur pour vérification.
    """
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_signature(secret_key: str, message: str, signature: str) -> bool:
    """Vérifie une signature en TEMPS CONSTANT.

    Pourquoi `hmac.compare_digest` et pas `==` : une comparaison naïve s'arrête au premier
    caractère différent, ce qui permet à un attaquant de deviner la signature octet par octet
    en mesurant le temps de réponse (attaque temporelle). `compare_digest` élimine ce canal.
    Exemple : comparer "abc123" à "abc999" prend plus de temps que comparer "xyz123" à "abc999"
    avec `==`, ce qui fuit de l'information.
    """
    expected = sign_message(secret_key, message)
    return hmac.compare_digest(expected, signature or "")


def build_session_canonical_string(
    project_id: str, exam_id: str, student_id: str, issued_at: int
) -> str:
    """Construit la chaîne canonique signée d'un jeton de session.

    Format fixé par 01_BACKEND.md §4.1 : `project_id|exam_id|student_id|issued_at`.
    L'ordre et le séparateur sont figés : toute divergence casserait la vérification.
    """
    return f"{project_id}|{exam_id}|{student_id}|{issued_at}"


def is_timestamp_fresh(issued_at: int, window_seconds: int) -> bool:
    """Vérifie que l'horodatage `issued_at` est dans la fenêtre de tolérance.

    Absorbe les dérives d'horloge entre le serveur du développeur et ExamSDK, tout en rejetant
    les jetons trop anciens (rejeu) ou trop dans le futur (horloge déréglée).
    Exemple : window=300 s → un jeton émis il y a 200 s est accepté, un jeton de 10 min est rejeté.
    """
    now = int(time.time())
    return abs(now - int(issued_at)) <= window_seconds
