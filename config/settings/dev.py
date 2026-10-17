"""
Réglages de développement local.

Surcharge `base.py` avec des valeurs pratiques pour coder hors ligne :
- DEBUG activé, hôtes larges ;
- emails affichés en console (pas d'envoi réel) ;
- clé de chiffrement Fernet jetable (les secrets chiffrés en dev ne valent rien) ;
- Celery en mode synchrone si Redis n'est pas lancé.
"""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = True

# En dev, accepter toutes les formes d'hôte (localhost, 127.0.0.1, IP du réseau local…).
ALLOWED_HOSTS = ["*"]

# Afficher les emails (vérification, réinitialisation) directement dans la console du runserver.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Clé Fernet de développement — VALEUR JETABLE, à ne jamais utiliser en production.
# En prod, prod.py refuse de démarrer si FIELD_ENCRYPTION_KEY n'est pas fournie.
if not FIELD_ENCRYPTION_KEY:  # noqa: F405
    FIELD_ENCRYPTION_KEY = "DhDMRVEz_RNRKmxcUEc_7Ha36fRTVtiMlCRAKlPdOEY="  # noqa: F405

# Logs plus verbeux pour repérer les erreurs pendant le développement.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
