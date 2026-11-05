import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.events.models import Event
from apps.sessions.models import ExamSession
from apps.sdklogs.models import SdkLog

print("== EVENTS ==")
for e in Event.objects.all().order_by("session", "occurred_at"):
    d = getattr(e, "description", None) or getattr(e, "label", None) or ""
    meta = (e.metadata or {}) if e.metadata else {}
    title = meta.get("title") or meta.get("message") or ""
    print(e.session_id, "|", e.type, "|", e.confidence_score, "|", str(title)[:80], "|", str(d)[:60], "| meta keys:", list(meta.keys())[:6])

print("\n== SESSIONS ==")
for s in ExamSession.objects.all():
    print(s.pk, s.project.name, s.status, "risk:", s.risk_score)

print("\n== SDKLOG (îlots) ==")
prev = None
for l in SdkLog.objects.order_by("received_at"):
    mark = "N" if l.level != prev else " "
    if mark == "N":
        print("---", l.level, "---")
        prev = l.level
print("total:", SdkLog.objects.count())
