import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.contrib.auth import get_user_model
from django.apps import apps

from apps.developers.models import Developer

for u in get_user_model().objects.all():
    dev = Developer.objects.filter(user=u).first()
    print("USER", u.pk, u.email, "staff:", u.is_staff, "super:", u.is_superuser, "dev:", (dev.status if dev else None))

P = apps.get_model("projects", "Project")
for p in P.objects.all():
    print("PROJ", p.pk, p.name, "public:", p.public_key[:12], "secret_last4:", p.secret_last4, "status:", p.status, "archived:", p.is_archived, "site:", p.site_url)

S = None
for m in apps.get_models():
    if m.__name__ == "ExamSession":
        S = m
print("SESS MODEL:", S)
for s in S.objects.all()[:12]:
    print("SESS", s.pk, s.project.name, s.exam_id, s.student_id, "status:", s.status, "risk:", getattr(s, "risk_score", None))

E = None
for m in apps.get_models():
    if m.__name__ == "Event":
        E = m
for e in E.objects.all()[:12]:
    d = getattr(e, "description", None) or getattr(e, "label", None) or ""
    print("EV", e.session.pk, e.type, d[:70])

L = None
for m in apps.get_models():
    if m.__name__ == "SdkLog":
        L = m
for l in L.objects.order_by("-received_at")[:8]:
    print("LOG", l.level, (l.message or "")[:60], l.received_at)
