"""Point d'entrée ASGI (déploiement async). Voir config/settings/prod.py."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
