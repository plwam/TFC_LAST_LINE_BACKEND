"""
Chiffrement au repos de `Project.secret_key` (01_BACKEND.md §12).

Pourquoi un champ custom plutôt qu'une librairie tierce : le besoin est une simple
symétrie Fernet (chiffrer à l'écriture, déchiffrer à la lecture) et l'usage est unique
(une seule colonne secrète). Cela évite d'ajouter une dépendance non validée.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    """Construit l'instance Fernet à partir de FIELD_ENCRYPTION_KEY.

    L'instanciation est faite à chaque appel (et non au chargement du module) pour que la
    valeur de réglage soit lue au moment de l'usage — utile pour les tests et pour éviter
    d'imposer la clé à l'import de Django.
    """
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


def encrypt_value(plaintext: str) -> str:
    """Chiffre une chaîne en clair et renvoie un jeton Fernet (str)."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Déchiffre un jeton Fernet.

    Renvoie le texte en clair si le jeton est valide. En cas de clé erronée (jeton illisible),
    on lève `InvalidToken` : c'est volontaire, cela signale une mauvaise configuration plutôt
    que de renvoyer silencieusement une valeur vide à la place d'un secret.
    """
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Impossible de déchiffrer la valeur (FIELD_ENCRYPTION_KEY incorrecte ?)."
        ) from exc


class EncryptedTextField(models.TextField):
    """Champ texte transparent : stocké chiffré en base, manipulé en clair en Python.

    - `get_prep_value` : appelé avant écriture en base → chiffre.
    - `from_db_value`   : appelé à la lecture → déchiffre.
    - `to_python`       : laissé tel quel pour ne PAS déchiffrer deux fois (Django appelle
      `to_python` après `from_db_value`).

    Exemple : `project.secret_key = "sk_live_abc"` → en base on stocke `gAAAAA…` (jeton
    Fernet) ; `Project.objects.get(...).secret_key` renvoie de nouveau `"sk_live_abc"`.
    """

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return encrypt_value(str(value))

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return decrypt_value(value)
        except ValueError:
            # Valeur non chiffrée trouvée en base (ex. donnée de test insérée à la main) :
            # on la renvoie telle quelle plutôt que de faire planter tout écran de détail.
            return value

    def to_python(self, value):
        return value
