"""
Vues DRF de l'API JWT (01_BACKEND.md §10).

Règles (01_BACKEND.md §7, §12) :
- la logique métier n'est PAS ici : création de projet et régénération de clé passent par
  `ProjectService` (le même service que les vues templates — jamais de duplication) ;
- isolation multi-tenant : chaque queryset est restreint via `for_tenant(developer)`, jamais
  un `get(pk=...)` nu (une ressource d'un autre développeur renvoie 404, pas 403).

Chaque endpoint est documenté (résumé + description + exemple) pour drf-spectacular.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.projects.models import Project
from apps.projects.services import ProjectService
from apps.sessions.models import ExamSession

from .serializers import EmailTokenObtainPairSerializer, ExamSessionSerializer, ProjectSerializer

TOKEN_TAG = "Authentification"
PROJECTS_TAG = "Projets"
SESSIONS_TAG = "Sessions"


@extend_schema(
    tags=[TOKEN_TAG],
    summary="Obtenir un jeton JWT (connexion par email)",
    description=(
        "Authentifie un développeur par **email + mot de passe** et renvoie un couple de jetons "
        "JWT (`access` court, `refresh` long). Contrairement à la connexion par session du "
        "tableau de bord, cette surface est destinée à de futurs clients non-navigateur "
        "(mobile, desktop, scripts).\n\n"
        "L'identifiant est l'**email** (et non le `username`). En cas d'échec, le message est "
        "toujours identique (`Identifiants invalides.`) afin de ne pas révéler si un compte "
        "existe. Le `access` se présente ensuite en en-tête `Authorization: Bearer <token>`."
    ),
    request=EmailTokenObtainPairSerializer,
    responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Connexion",
            value={"email": "dev@example.com", "password": "motdepasse"},
            request_only=True,
        ),
        OpenApiExample(
            "Jetons",
            value={"refresh": "eyJhbGciOiJIUzI1NiIs...", "access": "eyJhbGciOiJIUzI1NiIs..."},
            response_only=True,
        ),
    ],
)
class EmailTokenObtainPairView(TokenObtainPairView):
    """Obtention d'un JWT par email/mot de passe (équivalent JSON de la connexion, §10)."""

    serializer_class = EmailTokenObtainPairSerializer


@extend_schema(
    tags=[TOKEN_TAG],
    summary="Rafraîchir un jeton d'accès",
    description=(
        "Échange un jeton `refresh` encore valide contre un nouveau jeton `access`, sans "
        "redemander le mot de passe. À utiliser lorsque l'`access` (30 min) a expiré. Un "
        "`refresh` expiré (7 jours) oblige à se reconnecter."
    ),
    responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Rafraîchir",
            value={"refresh": "eyJhbGciOiJIUzI1NiIs..."},
            request_only=True,
        ),
        OpenApiExample("Nouveau jeton d'accès", value={"access": "eyJhbGciOiJIUzI1NiIs..."},
                       response_only=True),
    ],
)
class EmailTokenRefreshView(TokenRefreshView):
    """Rafraîchissement du JWT (délègue au comportement simplejwt)."""


class DeveloperScopedMixin:
    """Expose le `Developer` du demandeur. Un `User` sans profil renvoie 403 (jamais 500)."""

    @property
    def developer(self):
        developer = getattr(self.request.user, "developer_profile", None)
        if developer is None:
            # Cas théorique (futur rôle non-développeur) : on refuse proprement au lieu de
            # laisser une IntegrityError (FK `developer` non nulle) remonter en 500.
            raise PermissionDenied("Votre compte n'est pas rattaché à un espace développeur.")
        return developer


@extend_schema_view(
    list=extend_schema(
        tags=[PROJECTS_TAG],
        summary="Lister ses projets",
        description=(
            "Renvoie la liste des projets **non archivés** du développeur authentifié, du plus "
            "récent au plus ancien. Chaque projet expose sa clé publique et la forme masquée de "
            "sa clé secrète (`sk_live_••••1234`) — jamais la clé secrète en clair."
        ),
        responses={200: ProjectSerializer(many=True)},
    ),
    create=extend_schema(
        tags=[PROJECTS_TAG],
        summary="Créer un projet",
        description=(
            "Crée un projet et lui **génère immédiatement** un couple de clés (publique + "
            "secrète). La création et la génération des clés sont atomiques et passent par le "
            "même service que le tableau de bord. L'action est journalisée (`AccessLog`).\n\n"
            "La `secret_key` n'est renvoyée par AUCUN de ces endpoints en clair ; utilisez "
            "l'action dédiée de régénération (qui la renvoie une seule fois) ou la revelation du "
            "tableau de bord."
        ),
        request=ProjectSerializer,
        responses={201: ProjectSerializer},
        examples=[
            OpenApiExample(
                "Créer un projet",
                value={
                    "name": "Examens Univ-A",
                    "description": "Surveillance des partiels de maths",
                    "site_url": "https://examens.univ-a.edu",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Projet créé",
                value={
                    "id": "3c8e...",
                    "name": "Examens Univ-A",
                    "description": "Surveillance des partiels de maths",
                    "site_url": "https://examens.univ-a.edu",
                    "public_key": "pk_live_9f2c...",
                    "masked_secret": "sk_live_••••a1b2",
                    "is_archived": False,
                    "created_at": "2024-10-15T12:20:00Z",
                    "updated_at": "2024-10-15T12:20:00Z",
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=[PROJECTS_TAG],
        summary="Détail d'un projet",
        description=(
            "Renvoie les informations d'un projet du développeur. Un projet appartenant à un "
            "autre développeur renvoie **404** (jamais 403) : son existence n'est pas révélée."
        ),
        responses={200: ProjectSerializer},
    ),
    update=extend_schema(
        tags=[PROJECTS_TAG],
        summary="Modifier un projet (remplacement)",
        description=(
            "Met à jour les champs modifiables (`name`, `description`, `site_url`). Les clés et "
            "l'état d'archivage ne sont jamais modifiables par cet endpoint. Action journalisée."
        ),
        responses={200: ProjectSerializer},
    ),
    partial_update=extend_schema(
        tags=[PROJECTS_TAG],
        summary="Modifier un projet (partiel)",
        description="Comme la modification complète, mais ne touche que les champs fournis.",
        responses={200: ProjectSerializer},
    ),
    destroy=extend_schema(
        tags=[PROJECTS_TAG],
        summary="Archiver un projet (pas de suppression physique)",
        description=(
            "**Archive** le projet (équivalent fonctionnel de la suppression). Le projet "
            "disparaît des listes et ses clés cessent d'être acceptées, mais les sessions et "
            "événements déjà collectés sont **conservés** (un événement est une preuve, il n'est "
            "jamais supprimé). Une purge définitive relèverait d'une tâche de maintenance "
            "privilégiée distincte."
        ),
        responses={204: None},
    ),
    regenerate_secret=extend_schema(
        tags=[PROJECTS_TAG],
        summary="Régénérer la clé secrète",
        description=(
            "Génère un nouveau couple de clés pour le projet. L'ancienne `secret_key` devient "
            "**immédiatement invalide** : toute session signée avec elle cesse d'être acceptée "
            "(UC-3). La nouvelle clé est renvoyée **une seule fois**, ici, et la réponse n'est "
            "pas mise en cache (`Cache-Control: no-store`). L'opération est journalisée comme "
            "action sensible."
        ),
        request=None,
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Nouvelle clé",
                value={"secret_key": "sk_live_5f3a...a1b2"},
                response_only=True,
            ),
        ],
    ),
)
class ProjectViewSet(DeveloperScopedMixin, viewsets.ModelViewSet):
    """CRUD des projets + régénération de la clé secrète (§10)."""

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 404/403 gérés par `get_object` ; `for_tenant(None)` renverrait un queryset vide.
        developer = getattr(self.request.user, "developer_profile", None)
        return Project.objects.for_tenant(developer).filter(is_archived=False).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        """Crée un projet via le MÊME service que la vue template (jamais de logique dupliquée)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = ProjectService.create_project(self.developer, **serializer.validated_data)
        output = self.get_serializer(project)
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["post"], url_path="regenerate-secret")
    def regenerate_secret(self, request, pk=None):
        """Régénère la clé secrète (l'ancienne devient immédiatement invalide, UC-3)."""
        project = self.get_object()  # scopé : 404 si autre tenant
        secret_key = ProjectService.regenerate_secret_key(
            project, actor=request.user, request=request
        )
        # La clé n'est renvoyée QU'ICI, une seule fois, et la réponse ne doit pas être mise en
        # cache (même règle que l'endpoint `reveal-secret` du dashboard).
        response = Response({"secret_key": secret_key}, status=status.HTTP_200_OK)
        response["Cache-Control"] = "no-store"
        return response


@extend_schema_view(
    list=extend_schema(
        tags=[SESSIONS_TAG],
        summary="Lister ses sessions",
        description=(
            "Renvoie les sessions d'examen du développeur authentifié, de la plus récente à la "
            "plus ancienne, tous projets confondus. Chaque session indique son `status` "
            "(`active` / `closed` / `invalid`), sa durée calculée et son `risk_score` (indicateur "
            "d'aide à la décision, pas une preuve de fraude)."
        ),
        responses={200: ExamSessionSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=[SESSIONS_TAG],
        summary="Détail d'une session",
        description=(
            "Renvoie une session précise. Une session d'un autre développeur renvoie **404**. "
            "Les événements associés ne sont **pas** exposés par cette surface JWT : ils sont "
            "consommés via l'API machine HMAC ou consultés dans le tableau de bord."
        ),
        responses={200: ExamSessionSerializer},
    ),
)
class ExamSessionViewSet(
    DeveloperScopedMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """Consultation des sessions (lecture seule, §10). Les événements sont immuables."""

    serializer_class = ExamSessionSerializer
    permission_classes = [IsAuthenticated]
    # Attribut de classe utilisé par drf-spectacular pour typer le paramètre de chemin
    # (`get_queryset` dépend de la requête et n'est pas introspectable). Les vues réelles
    # passent toujours par `get_queryset` scopé.
    queryset = ExamSession.objects.all()

    def get_queryset(self):
        return ExamSession.objects.for_tenant(self.developer).select_related("project").order_by("-started_at")
