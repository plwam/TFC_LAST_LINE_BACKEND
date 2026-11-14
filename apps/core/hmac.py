"""
Primitives cryptographiques HMAC — API machine (SDK / LMS), 01_BACKEND.md §9, §12.

Modèle Zero Trust : aucune notion d'utilisateur connecté. Le serveur du développeur signe
un jeton de session avec sa `secret_key` ; ExamSDK revérifie la signature en temps constant.

Clés à deux niveaux : la clé maîtresse (`project.secret_key`) ne quitte JAMAIS le contexte
serveur après l'initiation — le SDK signe les événements avec une clé de session dérivée
(`derive_session_key`), scellée sur le `session_id` et morte à la clôture. La dérivation est
déterministe : RIEN à stocker, le backend recalcule la même clé à chaque vérification.
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


SESSION_KEY_LABEL = "session-key"


def derive_session_key(master_secret: str, session_id: str) -> str:
    """Dérive la clé de session (« clé de chambre ») d'une session : HMAC-SHA256 hexadécimal.

    Format figé : `HMAC-SHA256(master_secret, "session-key|<session_id>")`. Le libellé
    (`SESSION_KEY_LABEL`) sépare les domaines : la même clé maîtresse sert à signer des
    messages ET à dériver des clés, le libellé garantit qu'aucune sortie d'un domaine ne
    peut être réutilisée dans l'autre.

    Propriétés voulues :
      - déterministe → le backend RECALCULE la clé à chaque vérification : rien à stocker,
        aucune table de clés à purger, aucun secret de plus dans la base ;
      - scellée sur la session → la clé d'une session ne valide pas une autre ;
      - éphémère de fait → la clé ne sert qu'aux requêtes d'une session vivante ; à la
        clôture, la session n'est plus éligible et la clé n'a plus aucun pouvoir.

    La clé maîtresse n'est donc plus nécessaire au SDK après l'initiation : les événements
    et la clôture sont signés avec cette clé dérivée, qui ne peut ouvrir qu'une chambre.
    """
    return sign_message(master_secret, f"{SESSION_KEY_LABEL}|{session_id}")
