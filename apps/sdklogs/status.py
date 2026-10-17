"""
Calcul de l'état de fonctionnement du SDK d'un projet — `status.py`.

L'état est dérivé de la fraîcheur des HEARTBEATS, jamais déclaré par le client : un SDK peut se
croire vivant alors qu'il ne joint plus le serveur. On ne se fie donc qu'à l'horodatage de
RÉCEPTION (`SdkLog.received_at`), décidé par ExamSDK.

Trois états :
  - `offline`  : aucun heartbeat reçu dans la fenêtre → le SDK ne tourne pas (ou ne joint plus
    le serveur) ;
  - `degraded` : heartbeat récent MAIS au moins une erreur journalisée dans la fenêtre → le SDK
    tourne, mais en signalant un problème ;
  - `online`   : heartbeat récent et aucune erreur récente.

La fenêtre est `settings.SDK_HEARTBEAT_WINDOW_SECONDS` (la même que la cadence annoncée au SDK).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import SdkLog


@dataclass(frozen=True)
class SdkStatus:
    """État de fonctionnement d'un SDK, prêt à afficher."""

    state: str  # "online" | "degraded" | "offline"
    last_heartbeat: datetime | None
    last_seen: datetime | None
    recent_errors: int

    @property
    def is_offline(self) -> bool:
        return self.state == "offline"

    @property
    def is_online(self) -> bool:
        return self.state == "online"


def compute_sdk_status(project, *, now=None, window_seconds=None) -> SdkStatus:
    """Calcule l'état du SDK du projet à l'instant `now` (injectable pour les tests).

    Une seule requête agrégée par signal, donc coût constant quel que soit le nombre de logs.
    """
    now = now or timezone.now()
    window = window_seconds or settings.SDK_HEARTBEAT_WINDOW_SECONDS
    since = now - timedelta(seconds=window)

    logs = SdkLog.objects.filter(project=project)

    last_seen = logs.order_by("-received_at").values_list("received_at", flat=True).first()
    last_heartbeat = (
        logs.filter(kind=SdkLog.Kind.HEARTBEAT)
        .order_by("-received_at")
        .values_list("received_at", flat=True)
        .first()
    )

    heartbeat_fresh = last_heartbeat is not None and last_heartbeat >= since
    if not heartbeat_fresh:
        state = "offline"
        recent_errors = 0
    else:
        recent_errors = logs.filter(
            level=SdkLog.Level.ERROR, received_at__gte=since
        ).count()
        state = "degraded" if recent_errors else "online"

    return SdkStatus(
        state=state,
        last_heartbeat=last_heartbeat,
        last_seen=last_seen,
        recent_errors=recent_errors,
    )
