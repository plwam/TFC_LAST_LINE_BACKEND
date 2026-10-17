"""Documentation OpenAPI (Swagger/Redoc) — documente l'API JWT ET l'API machine (01 §2).

Les vues templates du dashboard ne sont volontairement PAS documentées ici : elles ne sont pas
destinées à être consommées par un tiers.

Accès protégé : ces interfaces exigent une connexion (développeur ou superutilisateur). Le
`login_required` redirige les anonymes vers la connexion ; `SERVE_AUTHENTICATION` +
`SERVE_PERMISSIONS` (dans `SPECTACULAR_SETTINGS`) appliquent la même règle côté DRF.
"""

from django.contrib.auth.decorators import login_required
from django.urls import path
from django.utils.decorators import method_decorator
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

app_name = "docs"


@method_decorator(login_required, name="dispatch")
class ProtectedSchemaView(SpectacularAPIView):
    """Schéma OpenAPI brut — réservé aux utilisateurs connectés."""


@method_decorator(login_required, name="dispatch")
class ProtectedSwaggerView(SpectacularSwaggerView):
    """Interface Swagger UI — réservée aux utilisateurs connectés."""


@method_decorator(login_required, name="dispatch")
class ProtectedRedocView(SpectacularRedocView):
    """Interface ReDoc — réservée aux utilisateurs connectés."""


urlpatterns = [
    path("schema/", ProtectedSchemaView.as_view(), name="schema"),
    path("swagger/", ProtectedSwaggerView.as_view(url_name="docs:schema"), name="swagger"),
    path("redoc/", ProtectedRedocView.as_view(url_name="docs:schema"), name="redoc"),
]
