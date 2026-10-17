"""
Réglages communs à tous les environnements — ExamSDK (cf. 01_BACKEND.md).

Ce module ne doit jamais être utilisé tel quel : `dev.py` et `prod.py` l'importent et le
surchargent. Toute valeur qui change entre dev et prod vit dans ces deux fichiers, pas ici.
"""

from datetime import timedelta
from pathlib import Path

import environ

# Chemin racine du backend : config/settings/base.py → remonte de 3 niveaux jusqu'à backend/.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Lecture des variables d'environnement (.env à la racine du backend, jamais versionné).
# Les valeurs par défaut sont sûres pour le développement ; en production elles DOIVENT
# être fournies explicitement (prod.py lève une erreur si une clé critique manque).
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Sécurité de base
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-dev-only-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    # API machine (HMAC) + API JWT (futurs clients) — 01_BACKEND.md §2.
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    # Authentification humaine : email/mdp + Google + GitHub — 01_BACKEND.md §4.
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    # Résultats de tâches asynchrones (score de risque) consultables depuis l'admin.
    "django_celery_results",
]

LOCAL_APPS = [
    "apps.accounts",       # User générique (AUTH_USER_MODEL)
    "apps.developers",     # Profil métier Developer
    "apps.administration", # Profil Administrator
    "apps.core",           # briques transverses (tenant scoping, HMAC, chiffrement)
    "apps.audit",          # AccessLog + middleware d'audit
    "apps.projects",       # Project, clés API, ProjectService
    "apps.sessions",       # ExamSession (app_label « examsessions », cf. apps/sessions/apps.py)
    "apps.events",         # Event, EventType, immuabilité
    "apps.dashboard",      # vues templates du tableau de bord
    "apps.api",            # API JWT (futurs clients mobile/desktop)
    "apps.machine_api",    # API HMAC (SDK / LMS)
    "apps.public",         # API publique (extension) : registered-hosts, health
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise n'est monté qu'en production (voir prod.py) : en dev, runserver sert les
    # statiques et WhiteNoise avertissait pour un STATIC_ROOT absent (bruit dans les tests).
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Obligatoire pour django-allauth : doit être APRÈS AuthenticationMiddleware.
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Audit : journalise les consultations/actions sensibles (AccessLog, BNF-33).
    "apps.audit.middleware.AccessLogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # `templates/` global (base, composants, surcharges allauth) — 06_FRONTEND_GUIDE.md §3.
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Expose `developer`, `developer_status` et `risk_thresholds` à tous les
                # templates du dashboard (06_FRONTEND_GUIDE.md §5.2).
                "apps.dashboard.context_processors.dashboard_context",
                # Expose `site_branding` (logo + nom éditables depuis l'admin) à TOUS les
                # templates : dashboard, surcharges allauth et landing publique.
                "apps.core.context_processors.site_branding",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Base de données — pilotée par DATABASE_URL (01_BACKEND.md §3, §14)
# En dev sans DATABASE_URL : SQLite. En prod : MySQL 8 (mysql://…), voir prod.py.
# ---------------------------------------------------------------------------
DATABASE_URL = env("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# Cache + Celery — Redis si REDIS_URL fourni, sinon repli local (dev sans Redis)
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    # Repli dev : cache en mémoire du process. Sufisant tant que Redis n'est pas lancé ;
    # la validation de token et la liste des hôtes publics n'ont pas besoin de persister.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "examsdk-locmem",
        }
    }

CELERY_BROKER_URL = REDIS_URL or "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "django-db"  # résultats stockés via django_celery_results
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
# Sans Redis lancé, on exécute les tâches en synchrone dans le process web : le score de
# risque est calculé immédiatement (dev). Avec REDIS_URL, la file reprend son rôle normal.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=not bool(REDIS_URL))
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------------------
# Authentification Django + allauth (01_BACKEND.md §4)
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SITE_ID = 1

# allauth 65 : `ACCOUNT_LOGIN_METHODS` (email seul comme identifiant) et
# `ACCOUNT_SIGNUP_FIELDS` remplacent les anciens ACCOUNT_AUTHENTICATION_METHOD /
# ACCOUNT_EMAIL_REQUIRED. Le « * » marque un champ obligatoire.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # email valide obligatoire avant 1re connexion (BF-01)
ACCOUNT_UNIQUE_EMAIL = True
# Un login Google/GitHub crée automatiquement le compte + le profil Developer (signal, §4).
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
# Redirections de la surface web (session) — le JWT de l'API suit un autre chemin.
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "dashboard:home"
ACCOUNT_LOGOUT_REDIRECT_URL = "account_login"
# Email de vérification envoyé en console en dev (voir dev.py) ; provider réel en prod.
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[ExamSDK] "

# Formulaires allauth rebranchés sur notre mixin Tailwind (apparence cohérente de tous les
# champs sans réécrire chaque gabarit). Voir apps/accounts/forms.py.
ACCOUNT_FORMS = {
    "login": "apps.accounts.forms.TailwindLoginForm",
    "signup": "apps.accounts.forms.TailwindSignupForm",
    "reset_password": "apps.accounts.forms.TailwindResetPasswordForm",
    "reset_password_from_key": "apps.accounts.forms.TailwindResetPasswordKeyForm",
    "change_password": "apps.accounts.forms.TailwindChangePasswordForm",
    "set_password": "apps.accounts.forms.TailwindSetPasswordForm",
}

# Providers sociaux : identifiants lus depuis l'environnement (jamais en dur, §14).
# Un provider sans identifiants n'apparaît pas sur la page de connexion : le dashboard
# reste fonctionnel en email/mdp tant que Google/GitHub ne sont pas configurés.
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "APP": {
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": env("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
        },
    },
    "github": {
        "SCOPE": ["user:email"],
        "APP": {
            "client_id": env("GITHUB_OAUTH_CLIENT_ID", default=""),
            "secret": env("GITHUB_OAUTH_CLIENT_SECRET", default=""),
        },
    },
}

# ---------------------------------------------------------------------------
# Django REST Framework — API JWT (futurs clients) + API machine HMAC
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# JWT développeur — clé de signature distincte du SECRET_KEY pour cloisonner les usages (§14).
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY", default=SECRET_KEY)
SIMPLE_JWT = {
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ExamSDK API",
    "DESCRIPTION": (
        "API JWT (clients développeur) et API machine HMAC (SDK / LMS). "
        "Le tableau de bord web n'est pas documenté ici (vues templates, session Django)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Regroupement des endpoints par domaine dans Swagger/ReDoc.
    "TAGS": [
        {"name": "Authentification", "description": "Obtention / rafraîchissement des jetons JWT développeur."},
        {"name": "Projets", "description": "CRUD des projets et cycle de vie des clés (API JWT)."},
        {"name": "Sessions", "description": "Consultation des sessions d'examen (API JWT, lecture seule)."},
        {"name": "Machine (HMAC)", "description": "Surface consommée par le SDK et le LMS, authentifiée par signature HMAC."},
        {"name": "Public", "description": "Endpoints sans authentification (extension navigateur, monitoring)."},
    ],
}

# ---------------------------------------------------------------------------
# Logique métier transverse
# ---------------------------------------------------------------------------
# Fenêtre de tolérance (secondes) sur l'horodatage `issued_at` d'un jeton de session HMAC :
# absorbe les dérives d'horloge entre le serveur du développeur et ExamSDK (§12, §14).
TOKEN_VALIDITY_WINDOW_SECONDS = env.int("TOKEN_VALIDITY_WINDOW_SECONDS", default=300)

# Plafond de requêtes par minute et par projet sur l'API machine HMAC (protection anti-boucle
# d'un SDK buggé, 01_BACKEND.md §12). Large en dev ; à calibrer en production.
MACHINE_RATE_LIMIT_PER_MINUTE = env.int("MACHINE_RATE_LIMIT_PER_MINUTE", default=600)

# Seuils d'interprétation du risk_score (06_FRONTEND_GUIDE.md §5.2). Valeurs indicatives,
# centralisées ici pour être calibrées après mesures réelles (Ch.3).
RISK_THRESHOLDS = {"medium": 0.3, "high": 0.6}

# Clé Fernet de chiffrement de `Project.secret_key` au repos (§12). En prod, prod.py exige
# une valeur fournie ; en dev, dev.py fournit une valeur jetable clairement marquée.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

# URL du CDN où est servi le SDK, injectée dans l'onglet « Intégration » (§8.6.4). Jamais
# codée en dur dans les templates.
SDK_CDN_URL = env("SDK_CDN_URL", default="https://cdn.examsdk.local/sdk/v1/examsdk.js")

# ---------------------------------------------------------------------------
# Internationalisation — interface en français, horodatages en UTC (06 §17 points 3-4)
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français"), ("en", "English")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# ---------------------------------------------------------------------------
# Fichiers statiques
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Stockage statique par défaut : simple. La production bascule sur le stockage compressé +
# manifeste de Whitenoise (voir prod.py), qui exige `collectstatic`.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# Fichiers médias téléversés (logo de l'identité visuelle, cf. apps.core.models.SiteBranding).
# En développement, config.urls sert MEDIA_URL ; en production, c'est le rôle du serveur web
# (Whitenoise ne sert QUE les fichiers statiques, pas les médias).
# ---------------------------------------------------------------------------
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
