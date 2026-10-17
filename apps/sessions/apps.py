"""Configuration de l'app `sessions` (modèle `ExamSession`)."""

from django.apps import AppConfig


class SessionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sessions"
    # Le label par défaut serait « sessions », DÉJÀ pris par `django.contrib.sessions`.
    # Deux apps ne peuvent pas partager un label (registre global) : on en déclare un distinct.
    # Conséquence assumée : tables `examsessions_*` et app_label « examsessions ».
    label = "examsessions"
    verbose_name = "sessions d'examen"
