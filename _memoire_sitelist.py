import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.projects.models import Project

p1 = Project.objects.get(name="UCS LMS")
p1.site_url = "https://lms.ucs.example/"
p1.save()
p2 = Project.objects.get(name="ULPGL LMS")
p2.site_url = "http://localhost:8080/"
p2.save()
print("site_url:", p1.site_url, "|", p2.site_url)
