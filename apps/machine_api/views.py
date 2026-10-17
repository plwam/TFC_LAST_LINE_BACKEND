"""
Vues de l'API machine HMAC (01_BACKEND.md §9).

| Méthode | Endpoint                                   | UC   |
|---------|--------------------------------------------|------|
| POST    | /api/v1/machine/sessions/                  | UC-5 |
| POST    | /api/v1/machine/sessions/{id}/close/       | UC-7 |
| POST    | /api/v1/machine/events/                    | UC-10|
| GET     | /api/v1/machine/events/?exam_id=&type=&student_id= | UC-6 |
| POST    | /api/v1/machine/logs/                      | —    |

Aucune logique de « projet » ici : ces vues ne manipulent que des sessions et des événements
appartenant au projet authentifié par HMAC (`request.auth.project`).

Chaque endpoint est documenté pour drf-spectacular (résumé + description + exemple) : le SDK et
l'intégrateur LMS sont des consommateurs tiers, la documentation fait partie du livrable.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event
from apps.sdklogs.models import SdkLog
from apps.sessions.models import ExamSession
from apps.sessions.tasks import compute_risk_score_task

from .authentication import HMACAuthentication, IsHMACAuthenticated
from .serializers import (
    EventBatchSerializer,
    EventReadSerializer,
    SdkLogBatchSerializer,
    SessionCloseSerializer,
    SessionCreateSerializer,
)

MACHINE_TAG = "Machine (HMAC)"


class MachineBaseView(APIView):
    """Base commune : authentification HMAC + permission projet signé."""

    authentication_classes = [HMACAuthentication]
    permission_classes = [IsHMACAuthenticated]

    @property
    def project(self):
        return self.request.auth.project


class MachineSessionCreateView(MachineBaseView):
    """OUVRE une session d'examen (UC-5). Idempotent : une session active identique est réutilisée.

    Pourquoi l'idempotence : si le SDK recharge la page d'examen, on ne veut pas multiplier les
    sessions pour le même couple (examen, étudiant) — sinon le tableau de bord deviendrait
    illisible et le score se diluerait sur plusieurs sessions.
    """

    @extend_schema(
        tags=[MACHINE_TAG],
        summary="Ouvrir une session d'examen",
        description=(
            "Ouvre une session pour un couple (examen, étudiant) et renvoie son identifiant, que "
            "le SDK réutilisera à chaque envoi d'événements. L'appel est **idempotent** : si une "
            "session ACTIVE existe déjà pour ce couple, elle est renvoyée telle quelle (HTTP 200) "
            "au lieu d'en créer une seconde (HTTP 201). Cela évite qu'un simple rechargement de "
            "la page d'examen ne crée des sessions en double.\n\n"
            "La requête doit être **signée** : en-têtes `X-ExamSDK-Public-Key` et "
            "`X-ExamSDK-Signature`, avec la chaîne canonique "
            "`project_id|exam_id|student_id|issued_at` (voir l'exemple)."
        ),
        request=SessionCreateSerializer,
        responses={
            201: OpenApiTypes.OBJECT,
            200: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Ouvrir une session",
                value={
                    "exam_id": "MATH-2024-S1",
                    "student_id": "etu-1042",
                    "issued_at": 1729000000,
                    "sdk_version": "1.2.0",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Session créée",
                value={
                    "session_id": "6f1c0f2a-3b6e-4c1a-9f2e-1a2b3c4d5e6f",
                    "status": "active",
                    "started_at": "2024-10-15T12:26:40Z",
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request):
        serializer = SessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = ExamSession.objects.filter(
            project=self.project,
            exam_id=data["exam_id"],
            student_id=data["student_id"],
            status=ExamSession.Status.ACTIVE,
        ).first()

        created = False
        if session is None:
            session = ExamSession.objects.create(
                project=self.project,
                exam_id=data["exam_id"],
                student_id=data["student_id"],
                status=ExamSession.Status.ACTIVE,
                started_at=data.get("started_at") or timezone.now(),
                sdk_version=data.get("sdk_version", ""),
            )
            created = True

        return Response(
            {
                "session_id": str(session.id),
                "status": session.status,
                "started_at": session.started_at,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MachineSessionCloseView(MachineBaseView):
    """FERME une session (UC-7). `invalid=true` la marque « Invalide » plutôt que « Terminée »."""

    @extend_schema(
        tags=[MACHINE_TAG],
        summary="Clôturer une session d'examen",
        description=(
            "Clôt une session ouverte. Par défaut la session devient `closed` (« Terminée ») ; "
            "avec `invalid: true` elle devient `invalid` (« Invalide ») — cas d'une session "
            "interrompue ou compromise, utilisable par un LMS qui constate une fraude. "
            "L'horodatage de fin (`ended_at`) n'est écrit qu'une seule fois : reclôturer une "
            "session ne réécrit pas sa fin.\n\n"
            "Une session appartenant à un autre projet renvoie **404** (jamais 403) : on ne "
            "révèle pas l'existence d'une ressource d'un autre développeur."
        ),
        request=SessionCloseSerializer,
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample("Clôturer normalement", value={"invalid": False}, request_only=True),
            OpenApiExample(
                "Marquer invalide",
                value={"invalid": True, "issued_at": 1729003600, "session_id": "6f1c0f2a-3b6e-4c1a-9f2e-1a2b3c4d5e6f"},
                request_only=True,
            ),
            OpenApiExample(
                "Session clôturée",
                value={"session_id": "6f1c0f2a-3b6e-4c1a-9f2e-1a2b3c4d5e6f", "status": "closed"},
                response_only=True,
            ),
        ],
    )
    def post(self, request, pk):
        # Scoping par projet : une session d'un autre projet renvoie 404 (jamais 403).
        session = ExamSession.objects.filter(project=self.project, pk=pk).first()
        if session is None:
            return Response({"detail": "Session introuvable."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SessionCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session.status = (
            ExamSession.Status.INVALID if serializer.validated_data["invalid"]
            else ExamSession.Status.CLOSED
        )
        # On ne réécrit `ended_at` que s'il n'était pas déjà fixé (une session close reste close).
        if session.ended_at is None:
            session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])
        return Response({"session_id": str(session.id), "status": session.status})


def _event_belongs_to_project(request, session_id):
    """Vérifie que `session_id` appartient bien au projet signé (sinon 404)."""
    return ExamSession.objects.filter(project=request.auth.project, pk=session_id).first()


class MachineEventsView(MachineBaseView):
    """Ingestion (POST) et consultation (GET) des événements (UC-10, UC-6)."""

    @extend_schema(
        tags=[MACHINE_TAG],
        summary="Envoyer un lot d'événements",
        description=(
            "Ingère un **lot** d'événements de surveillance pour une session (le SDK regroupe "
            "plusieurs détections dans un même envoi réseau). L'ingestion est **idempotente par "
            "`event_id`** : un renvoi réseau du même lot ne crée pas de doublon, il est compté dans "
            "`duplicates`. Chaque événement est inséré dans sa propre transaction, un doublon "
            "isolé n'échoue donc pas tout le lot.\n\n"
            "La réponse renvoie `accepted` et `duplicates` (HTTP 202). Après acceptation, le "
            "score de risque de la session est recalculé en tâche de fond (jamais dans le chemin "
            "de la réponse). La signature couvre la chaîne "
            "`project_id|session_id|issued_at`."
        ),
        request=EventBatchSerializer,
        responses={202: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Lot de deux événements",
                value={
                    "session_id": "6f1c0f2a-3b6e-4c1a-9f2e-1a2b3c4d5e6f",
                    "issued_at": 1729000100,
                    "events": [
                        {
                            "event_id": "e-0001",
                            "type": "FOCUS_LOST",
                            "source": "sdk",
                            "occurred_at": "2024-10-15T12:28:00Z",
                        },
                        {
                            "event_id": "e-0002",
                            "type": "GAZE_AWAY_SUSTAINED",
                            "source": "sdk",
                            "confidence_score": 0.87,
                            "metadata": {"durationMs": 3400, "gaze": {"yawDeg": 32, "pitchDeg": 5}},
                            "occurred_at": "2024-10-15T12:28:05Z",
                        },
                    ],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Lot accepté",
                value={"accepted": 2, "duplicates": 0},
                response_only=True,
                status_codes=["202"],
            ),
        ],
    )
    def post(self, request):
        session_id = request.data.get("session_id")
        session = _event_belongs_to_project(request, session_id)
        if session is None:
            return Response({"detail": "Session introuvable."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EventBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        accepted, duplicates = 0, 0
        # Chaque événement est créé dans sa propre transaction : un doublon (même event_id déjà
        # connu) ne doit pas faire échouer tout le lot (idempotence réseau, contrainte d'unicité).
        for item in serializer.validated_data["events"]:
            try:
                with transaction.atomic():
                    Event.objects.create(session=session, **item)
                accepted += 1
            except IntegrityError:
                duplicates += 1

        # Recalcul du score en tâche de fond : jamais dans le chemin de la réponse HTTP.
        # `.delay()` exécute en synchrone si CELERY_TASK_ALWAYS_EAGER (dev sans Redis).
        if accepted:
            compute_risk_score_task.delay(str(session.id))

        return Response(
            {"accepted": accepted, "duplicates": duplicates},
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        tags=[MACHINE_TAG],
        summary="Consulter les événements d'un projet",
        description=(
            "Renvoie les événements du projet authentifié, du plus récent au plus ancien "
            "(500 au maximum). Les filtres `exam_id`, `student_id` et `type` permettent de cibler "
            "une passation précise ou un type de détection (ex. tous les `MULTIPLE_FACES` d'un "
            "examen). Aucun événement d'un autre projet n'est jamais retourné : le résultat est "
            "scopé sur le projet de la signature."
        ),
        parameters=[
            OpenApiParameter("exam_id", OpenApiTypes.STR, OpenApiParameter.QUERY,
                             description="Filtre sur l'identifiant d'examen."),
            OpenApiParameter("student_id", OpenApiTypes.STR, OpenApiParameter.QUERY,
                             description="Filtre sur l'identifiant d'étudiant."),
            OpenApiParameter("type", OpenApiTypes.STR, OpenApiParameter.QUERY,
                             description="Filtre sur un type d'événement (ex. FOCUS_LOST)."),
        ],
        responses={200: EventReadSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Deux événements",
                value=[
                    {
                        "id": "9c2f...",
                        "event_id": "e-0002",
                        "type": "GAZE_AWAY_SUSTAINED",
                        "source": "sdk",
                        "confidence_score": 0.87,
                        "sdk_version": "1.2.0",
                        "integrity_hash": "",
                        "metadata": {"durationMs": 3400},
                        "occurred_at": "2024-10-15T12:28:05Z",
                    }
                ],
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        # Consultation scopée sur le projet signé, avec les filtres de 01_BACKEND.md §9.
        events = Event.objects.filter(session__project=self.project).select_related("session")
        exam_id = request.query_params.get("exam_id")
        event_type = request.query_params.get("type")
        student_id = request.query_params.get("student_id")
        if exam_id:
            events = events.filter(session__exam_id=exam_id)
        if student_id:
            events = events.filter(session__student_id=student_id)
        if event_type:
            events = events.filter(type=event_type)
        events = events.order_by("-occurred_at")[:500]
        return Response(EventReadSerializer(events, many=True).data)


class MachineLogsView(MachineBaseView):
    """Ingestion du JOURNAL DE FONCTIONNEMENT du SDK (heartbeats + logs).

    Permet au développeur de suivre la santé de son SDK depuis le dashboard : le SDK pousse
    régulièrement un signal de vie (`kind=heartbeat`) et, à sa convenance, des messages de
    journal (`kind=log`) avec un niveau.
    """

    @extend_schema(
        tags=[MACHINE_TAG],
        summary="Envoyer le journal de fonctionnement du SDK",
        description=(
            "Ingère un **lot** d'entrées de journal du SDK : des **signaux de vie** "
            "(`kind=heartbeat`) et/ou des **messages** (`kind=log`) avec un niveau "
            "(`debug` | `info` | `warning` | `error`). Le développeur les consulte en temps réel "
            "dans l'onglet « Journal SDK » de son projet, qui en déduit un état en ligne / "
            "dégradé / hors ligne à partir de la fraîcheur du dernier heartbeat.\n\n"
            "Le champ `session_id` est **facultatif** : il rattache les entrées à une passation "
            "précise (une session d'un autre projet renvoie `404`). La signature couvre la chaîne "
            "canonique `project_id|sdk-logs|issued_at` — différente de celle des événements, car "
            "un heartbeat peut précéder l'ouverture d'une session. La réponse renvoie le nombre "
            "d'entrées acceptées (HTTP 202)."
        ),
        request=SdkLogBatchSerializer,
        responses={202: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Un heartbeat et une erreur",
                value={
                    "issued_at": 1729000200,
                    "session_id": "6f1c0f2a-3b6e-4c1a-9f2e-1a2b3c4d5e6f",
                    "logs": [
                        {
                            "kind": "heartbeat",
                            "level": "info",
                            "sdk_version": "1.2.0",
                            "occurred_at": "2024-10-15T12:30:00Z",
                        },
                        {
                            "kind": "log",
                            "level": "error",
                            "message": "Caméra indisponible (NotReadableError).",
                            "sdk_version": "1.2.0",
                            "context": {"device": "webcam", "attempt": 3},
                            "occurred_at": "2024-10-15T12:30:02Z",
                        },
                    ],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Lot accepté",
                value={"accepted": 2},
                response_only=True,
                status_codes=["202"],
            ),
        ],
    )
    def post(self, request):
        serializer = SdkLogBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Rattachement facultatif à une session : même règle de scoping que les événements
        # (une session d'un autre projet renvoie 404, jamais 403).
        session = None
        session_id = data.get("session_id")
        if session_id:
            session = ExamSession.objects.filter(project=self.project, pk=session_id).first()
            if session is None:
                return Response({"detail": "Session introuvable."}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        # Création en masse : le journal est en écriture seule, mais l'ingestion peut légitimement
        # insérer plusieurs milliers d'entrées ; on évite N requêtes d'insertion.
        SdkLog.objects.bulk_create(
            [
                SdkLog(
                    project=self.project,
                    session=session,
                    level=item["level"],
                    kind=item["kind"],
                    message=item.get("message", ""),
                    sdk_version=item.get("sdk_version", ""),
                    context=item.get("context") or {},
                    occurred_at=item.get("occurred_at") or now,
                )
                for item in data["logs"]
            ]
        )
        return Response({"accepted": len(data["logs"])}, status=status.HTTP_202_ACCEPTED)
