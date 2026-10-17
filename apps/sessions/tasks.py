"""
Tâches Celery de l'app `sessions` (01_BACKEND.md §2, §9).

Le calcul du score ne doit JAMAIS bloquer la réponse HTTP d'ingestion d'événements : il part en
tâche asynchrone. En dev sans Redis, `CELERY_TASK_ALWAYS_EAGER` l'exécute immédiatement dans le
process web (comportement transparent pour l'appelant).
"""

from celery import shared_task

from .models import ExamSession
from .risk import compute_risk_score


@shared_task(name="sessions.compute_risk_score")
def compute_risk_score_task(session_id) -> float | None:
    """Recalcule et enregistre le `risk_score` d'une session (BF-16).

    Renvoie le score, ou None si la session n'existe plus (ex. projet archivé/purgé entre-temps).
    """
    session = ExamSession.objects.filter(pk=session_id).first()
    if session is None:
        return None
    score = compute_risk_score(session.events.all())
    session.risk_score = score
    session.save(update_fields=["risk_score", "updated_at"])
    return score
