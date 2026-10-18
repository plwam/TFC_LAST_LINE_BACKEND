"""
Routage racine — séparation stricte entre surfaces (01_BACKEND.md §6).

| Préfixe            | Surface                                   | Authentification      |
|--------------------|-------------------------------------------|-----------------------|
| /accounts/         | Connexion/inscription/reset (allauth)     | session (cookies)     |
| /dashboard/        | Tableau de bord développeur (templates)   | session + LoginRequired|
| /admin/            | Django Admin natif (UC-11 à UC-13)        | session + is_staff    |
| /api/v1/           | API JWT (futurs clients mobile/desktop)   | JWT                   |
| /api/v1/machine/   | API machine (SDK / LMS)                   | HMAC                  |
| /public/           | API publique (extension)                  | aucune                |
| /docs/             | Swagger/Redoc (API JWT + machine)         | aucune                |

ÉTAPE 2 branchera les préfixes api/, machine/, public/ et docs/. Pour l'instant, seuls les
templates (accounts/dashboard/admin) sont câblés, conformément au découpage par points de
contrôle.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.administration.admin import metrics_view
from apps.core.views import LandingView
from apps.public.views import HealthView

# En-tête du Django Admin (06_FRONTEND_GUIDE.md §8.11) — seule personnalisation de l'admin.
admin.site.site_header = "EvaSee — Administration"
admin.site.site_title = "EvaSee"

urlpatterns = [
    # Racine : page d'accueil PUBLIQUE pour un visiteur, redirection vers le dashboard si connecté.
    path("", LandingView.as_view(), name="root"),
    path("accounts/", include("allauth.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    # Vue de métriques admin (UC-13) — AVANT l'admin, sinon le préfixe `admin/` l'intercepterait.
    path("admin/metrics/", metrics_view, name="admin-metrics"),
    path("admin/", admin.site.urls),
    # --- Surface API (étape 2) ---
    path("api/v1/", include("apps.api.urls")),
    path("api/v1/machine/", include("apps.machine_api.urls")),
    path("public/", include("apps.public.urls")),
    path("docs/", include("apps.api.docs_urls")),
    # Sonde de monitoring à la racine (convention d'hébergement), en plus de /public/health/.
    path("health/", HealthView.as_view(), name="health"),
]

# Médias téléversés (logo) : servis par Django UNIQUEMENT en développement (DEBUG=True).
# `static()` renvoie [] en production — c'est alors le serveur web qui sert MEDIA_URL.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
