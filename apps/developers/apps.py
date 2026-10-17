from django.apps import AppConfig


class DevelopersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.developers"
    verbose_name = "Profils développeur"

    def ready(self):
        # Import des signaux au démarrage de l'app : sans cela, le signal `user_signed_up`
        # ne serait jamais connecté et aucun profil Developer ne serait créé (voir signals.py).
        from . import signals  # noqa: F401
