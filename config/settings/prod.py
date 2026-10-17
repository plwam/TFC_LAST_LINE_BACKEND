"""
Réglages de production.

Règle : aucune valeur secrète par défaut. Si une variable critique manque, on lève une erreur
au démarrage plutôt que de démarrer en silence avec une configuration dangereuse.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# En production, les hôtes autorisés DOIVENT être fournis explicitement (liste séparée par virgules).
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS doit être défini en production.")

# Base MySQL 8 obligatoire en production (01_BACKEND.md §3, §7 des guidelines).
if not env("DATABASE_URL", default=""):
    raise ImproperlyConfigured("DATABASE_URL (mysql://…) doit être défini en production.")

# Clé de chiffrement obligatoire : sans elle, impossible de relire les secret_key existantes.
if not env("FIELD_ENCRYPTION_KEY", default=""):
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY doit être défini en production.")

# Emails réels via SMTP (EMAIL_BACKEND_URL au format smtp://user:pass@host:port).
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@examsdk.example")

# --- Fichiers statiques : stockage compressé + manifeste (Whitenoise), nécessite collectstatic ---
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# WhiteNoise (service des fichiers statiques collectés) n'est activé qu'en production ; il est
# inséré juste après SecurityMiddleware, comme dans la configuration Django recommandée.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# --- Durcissement sécurité (derrière un reverse proxy TLS) ---
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Logs de production ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
