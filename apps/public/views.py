"""
API publique — sans authentification (01_BACKEND.md §11).

Deux endpoints, volontairement minimaux :
- `/public/registered-hosts/` : consommé par l'extension (03_EXTENSION.md §5). Renvoie la
  liste des domaines autorisés, dérivée des `site_url` des projets NON archivés. Aucune donnée
  sensible n'est exposée (jamais les clés, jamais les identifiants de projet).
- `/public/health/` : sonde de monitoring.

Minimisation : on n'expose que des NOMS D'HÔTES (jamais l'URL complète ni de chemin), et la
liste est mise en cache quelques minutes pour éviter de marteler la base à chaque démarrage
d'extension.

Ces vues sont écrites avec DRF (et non de simples `JsonResponse`) pour apparaître dans la
documentation OpenAPI générée par drf-spectacular : l'extension navigateur est un consommateur
tiers, ses endpoints doivent donc être documentés.
"""

from urllib.parse import urlparse

from django.core.cache import cache
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

# Durée du cache : compromis entre fraîcheur (un nouveau domaine doit être reconnu vite) et
# charge (l'extension interroge cet endpoint à chaque navigation). 5 minutes suffisent.
REGISTERED_HOSTS_CACHE_SECONDS = 300
REGISTERED_HOSTS_CACHE_KEY = "public:registered-hosts:v1"


@extend_schema(
    tags=["Public"],
    summary="Hôtes autorisés (pour l'extension navigateur)",
    description=(
        "Renvoie la liste des **noms d'hôtes** sur lesquels l'extension de surveillance doit "
        "s'activer. La liste est dérivée des `site_url` des projets **non archivés** : dès qu'un "
        "projet est archivé (sa « suppression »), son domaine disparaît de cette réponse et "
        "l'extension cesse d'y déployer la surveillance.\n\n"
        "Aucune authentification n'est requise — l'extension embarque cette URL publique. Par "
        "minimisation, seuls les noms d'hôtes sont exposés (jamais l'URL complète, jamais un "
        "chemin, jamais une clé ni un identifiant de projet). La réponse est mise en cache 5 "
        "minutes côté serveur et accompagnée d'un `Cache-Control` court côté navigateur, afin de "
        "ne pas solliciter la base à chaque navigation de l'étudiant."
    ),
    responses={200: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Deux domaines autorisés",
            value={"hosts": ["examens.univ-a.edu", "examens.univ-b.edu"], "count": 2},
            response_only=True,
        ),
    ],
)
class RegisteredHostsView(APIView):
    """Liste des hôtes autorisés par l'extension (domaines des projets actifs)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        hosts = cache.get(REGISTERED_HOSTS_CACHE_KEY)
        if hosts is None:
            site_urls = (
                Project.objects.filter(is_archived=False)
                .values_list("site_url", flat=True)
                .distinct()
            )
            # On normalise en nom d'hôte et on déduplique : deux projets sur le même domaine ne
            # doivent produire qu'une seule entrée.
            hosts = sorted({urlparse(url).hostname for url in site_urls if urlparse(url).hostname})
            cache.set(REGISTERED_HOSTS_CACHE_KEY, hosts, REGISTERED_HOSTS_CACHE_SECONDS)

        response = Response({"hosts": hosts, "count": len(hosts)})
        # Réponse publique destinée à l'extension : autorise un cache navigateur court en plus
        # du cache serveur (permet des rechargements d'extension sans requête systématique).
        response["Cache-Control"] = f"public, max-age={REGISTERED_HOSTS_CACHE_SECONDS}"
        return response


@extend_schema(
    tags=["Public"],
    summary="Sonde de disponibilité (monitoring)",
    description=(
        "Endpoint trivial de type *health check*, destiné aux outils de supervision (et à la "
        "plateforme d'hébergement). Il **ne touche pas la base de données** : il répond dès lors "
        "que le processus web est vivant, ce qui permet de distinguer une panne d'application "
        "d'une panne de base.\n\n"
        "La forme de la réponse est volontairement stable (`{\"status\": \"ok\"}`) pour être "
        "consommée par un simple test `HTTP 200`. Le même contrôle est aussi exposé à la racine "
        "`/health/`."
    ),
    responses={200: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample("Service disponible", value={"status": "ok"}, response_only=True),
    ],
)
class HealthView(APIView):
    """Sonde de disponibilité (monitoring)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})
