"""Configuration de l'app `sdklogs` (modèle `SdkLog`)."""

from django.apps import AppConfig


class SdklogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sdklogs"
    verbose_name = "journal du SDK"
