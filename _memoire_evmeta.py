import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.events.models import Event

e = Event.objects.filter(type__in=["WARNING_ISSUED", "OBJECT_DETECTED", "HANDS_VISIBLE_SUSTAINED"]).first()
print(e.type)
import json

for e in Event.objects.all():
    m = e.metadata or {}
    if e.type in ("WARNING_ISSUED", "OBJECT_DETECTED", "HANDS_VISIBLE_SUSTAINED", "FOCUS_LOST", "TAB_SWITCH"):
        print(e.type, "=>", json.dumps(m.get("messageText") or m, ensure_ascii=False)[:220])
