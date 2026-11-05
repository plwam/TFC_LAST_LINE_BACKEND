import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.contrib.auth import get_user_model

U = get_user_model()
u = U.objects.get(email="lwanzopaterne@gmail.com")
u.set_password("pat18er03n@2004")
u.save()
print("Mot de passe du développeur restauré (compte existant utilisé).")
