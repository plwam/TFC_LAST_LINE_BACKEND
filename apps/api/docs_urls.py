"""Documentation OpenAPI (Swagger/Redoc) — documente l'API JWT ET l'API machine (01 §2).

Les vues templates du dashboard ne sont volontairement PAS documentées ici : elles ne sont pas
destinées à être consommées par un tiers.
"""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

app_name = "docs"

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="docs:schema"), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(url_name="docs:schema"), name="redoc"),
]
