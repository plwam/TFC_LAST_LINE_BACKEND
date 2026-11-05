import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import hashlib
import hmac
import json
import time
import urllib.request
from cryptography.fernet import Fernet

from django.conf import settings
from apps.projects.models import Project

from django.db import connection

p = Project.objects.get(name="UCS LMS")
with connection.cursor() as cur:
    cur.execute("SELECT secret_key FROM projects_project WHERE name = %s", ["UCS LMS"])
    row = cur.fetchone()
raw = row[0]
print("raw prefix:", raw[:10], "len:", len(raw))
if raw.startswith("gAAAAA"):
    fernet = Fernet(settings.FIELD_ENCRYPTION_KEY)
    secret = fernet.decrypt(raw.encode()).decode()
else:
    secret = raw
secret = str(secret)
print("public:", p.public_key)
print("secret len:", len(secret), "prefix:", secret[:8])

pid = str(p.id)
issued = int(time.time())
canonical = f"{pid}|sdk-logs|{issued}"
sig = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()

now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
payload = {
    "issued_at": issued,
    "logs": [
        {"kind": "heartbeat", "level": "info", "sdk_version": "1.0.0", "occurred_at": now_iso},
        {"kind": "log", "level": "info", "message": "Session démarrée.", "sdk_version": "1.0.0", "occurred_at": now_iso, "context": {"module": "core"}},
        {"kind": "log", "level": "info", "message": "Modèle FaceMesh chargé en 1840 ms.", "sdk_version": "1.0.0", "occurred_at": now_iso, "context": {"module": "vision"}},
        {"kind": "log", "level": "info", "message": "Caméra et micro autorisés.", "sdk_version": "1.0.0", "occurred_at": now_iso, "context": {"module": "consent"}},
        {"kind": "log", "level": "info", "message": "Aperçu et bandeau affichés au candidat.", "sdk_version": "1.0.0", "occurred_at": now_iso, "context": {"module": "ui"}},
    ],
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/machine/logs/",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "X-ExamSDK-Public-Key": p.public_key,
        "X-ExamSDK-Signature": sig,
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=10) as r:
    print("HTTP", r.status, r.read().decode())
