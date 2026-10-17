"""Configuration de l'app `events` (modèle `Event`)."""

from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"
    verbose_name = "événements"
