"""URLs de l'API JWT (01_BACKEND.md §10). Toutes sous `/api/v1/`."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.api.views import EmailTokenObtainPairView, EmailTokenRefreshView, ExamSessionViewSet, ProjectViewSet

app_name = "api"

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("sessions", ExamSessionViewSet, basename="session")

urlpatterns = [
    # Obtention / rafraîchissement du token JWT (équivalent JSON de la connexion).
    path("auth/token/", EmailTokenObtainPairView.as_view(), name="token-obtain"),
    path("auth/token/refresh/", EmailTokenRefreshView.as_view(), name="token-refresh"),
    path("", include(router.urls)),
]
