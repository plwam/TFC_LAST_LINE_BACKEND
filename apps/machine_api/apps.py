"""Configuration de l'app `machine_api` (API HMAC consommée par le SDK et le LMS)."""

from django.apps import AppConfig


class MachineApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.machine_api"
    verbose_name = "API machine (HMAC)"

    def ready(self):
        # Import de l'extension OpenAPI : drf-spectacular découvre les extensions importées,
        # ce qui fait apparaître le schéma d'authentification HMAC dans Swagger/ReDoc.
        from . import schema  # noqa: F401
