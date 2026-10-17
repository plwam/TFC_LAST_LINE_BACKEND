"""Configuration de l'app `api` (API JWT pour futurs clients mobile/desktop)."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    verbose_name = "API développeur (JWT)"
