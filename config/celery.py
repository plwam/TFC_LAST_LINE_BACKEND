"""
Application Celery — tâches asynchrones (score de risque, emails).

Lancement du worker (Redis requis) : `celery -A config worker -l info`
En dev sans Redis, CELERY_TASK_ALWAYS_EAGER exécute les tâches dans le process web (voir base.py).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("examsdk")
# Tous les réglages CELERY_* de settings.py sont repris automatiquement (préfixe CELERY_).
app.config_from_object("django.conf:settings", namespace="CELERY")
# Découvre les tâches dans les fichiers `tasks.py` de chaque app installée.
app.autodiscover_tasks()
