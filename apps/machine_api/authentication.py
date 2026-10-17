"""
Authentification HMAC de l'API machine — modèle Zero Trust (01_BACKEND.md §1, §9, §12).

Aucune notion d'utilisateur connecté : ce n'est pas une session Django ni un JWT, c'est une
signature cryptographique vérifiable. Le serveur du développeur (ou le LMS) signe une chaîne
canonique avec sa `secret_key` ; ExamSDK ne fait confiance à RIEN d'autre que cette signature.

Contrat de requête (à confirmer avec `02_SDK.md` §14 — voir avertissement ci-dessous) :
  En-têtes :
    - `X-ExamSDK-Public-Key` : `project.public_key` (identifie le projet, jamais secret) ;
    - `X-ExamSDK-Signature`  : HMAC-SHA256 hexadécimal.
  Corps JSON : contient `issued_at` (epoch secondes) et, selon l'endpoint :
    - création de session  → `exam_id`, `student_id`  ⇒ canonique `project_id|exam_id|student_id|issued_at` ;
    - envoi d'événements   → `session_id`             ⇒ canonique `project_id|session_id|issued_at` ;
    - journal du SDK       → (endpoint /machine/logs/) ⇒ canonique `project_id|sdk-logs|issued_at`.

AVERTISSEMENT : la chaîne canonique de création de session est explicitement figée par
`01_BACKEND.md` §4.1. Celle des événements n'est pas spécifiée dans les documents accessibles ;
on la définit ici de la façon la plus simple et on la SIGNALE comme point à valider avant
d'écrire le SDK (`05_AGENT_GUIDELINES.md` §5, §9).
"""

from django.conf import settings
from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from apps.core.hmac import build_session_canonical_string, is_timestamp_fresh, verify_signature
from apps.projects.models import Project


class AuthenticatedProject:
    """Objet renvoyé dans `request.auth` : le projet authentifié par sa signature."""

    def __init__(self, project: Project):
        self.project = project
        self.id = project.id

    def __str__(self):
        return f"machine:{self.project.public_key}"


class HMACAuthentication(BaseAuthentication):
    """Vérifie la signature HMAC d'une requête de machine."""

    def authenticate_header(self, request):
        """Renvoyé par DRF sur échec d'authentification → réponse 401 (et non 403).

        Sans en-tête `WWW-Authenticate`, DRF convertirait un `AuthenticationFailed` en 403, ce
        qui brouille la distinction entre « non authentifié » (401) et « interdit » (403).
        """
        return "HMAC"

    @staticmethod
    def _payload(request) -> dict:
        """Fusionne query params + corps JSON en un dict (les deux surfaces sont signables).

        Pourquoi : une requête GET (`events/?exam_id=…`) n'a pas de corps, donc `request.data`
        est vide — les champs signés arrivent par l'URL. Une requête POST les porte dans le
        corps. On accepte les deux de façon uniforme.
        """
        data = {}
        query = request.query_params
        if hasattr(query, "dict"):
            data.update(query.dict())
        body = request.data
        if isinstance(body, dict):
            data.update(body)
        return data

    def authenticate(self, request):
        public_key = request.headers.get("X-ExamSDK-Public-Key")
        signature = request.headers.get("X-ExamSDK-Signature")
        # Pas d'en-têtes machine → ce n'est pas ce schéma d'authentification (DRF essaiera le
        # suivant). On ne lève PAS d'erreur ici, pour ne pas casser d'éventuels autres usages.
        if not public_key or not signature:
            return None

        # Un projet archivé, suspendu ou désactivé est refusé exactement comme un projet inconnu :
        # ses clés ne doivent plus rien valider. L'archivage remplace la « suppression » (§17 p.1) ;
        # la suspension/désactivation est une coupure réversible décidée par le développeur ou
        # l'administration (message volontairement générique : on ne révèle pas l'état du projet).
        project = Project.objects.filter(
            public_key=public_key,
            is_archived=False,
            status=Project.Status.ACTIVE,
        ).first()
        if project is None:
            raise AuthenticationFailed("Clé publique inconnue ou projet inactif.")

        data = self._payload(request)
        issued_at = data.get("issued_at")
        if issued_at is None:
            raise AuthenticationFailed("Champ `issued_at` manquant : requête non signable.")

        message = self._canonical_string(request, project, data)
        if message is None:
            raise AuthenticationFailed("Champs requis manquants pour reconstruire la signature.")

        # Comparaison en TEMPS CONSTANT (hmac.compare_digest) : voir apps/core/hmac.py.
        if not verify_signature(str(project.secret_key), message, signature):
            raise AuthenticationFailed("Signature invalide.")

        try:
            fresh = is_timestamp_fresh(int(issued_at), settings.TOKEN_VALIDITY_WINDOW_SECONDS)
        except (TypeError, ValueError):
            raise AuthenticationFailed("`issued_at` invalide.")
        if not fresh:
            raise AuthenticationFailed("Jeton expiré ou horodatage hors tolérance.")

        self._enforce_rate_limit(project)
        # `request.user` reste None (pas d'utilisateur humain) ; `request.auth` porte le projet.
        return (None, AuthenticatedProject(project))

    @staticmethod
    def _canonical_string(request, project: Project, data: dict):
        """Reconstruit la chaîne canonique signée, ou None si les champs requis manquent.

        L'endpoint est déterminé en premier : le journal SDK a sa propre canonique, car un
        heartbeat peut être envoyé AVANT l'ouverture d'une session (pas de `session_id`). Sans
        ce test prioritaire, un lot de logs portant un `session_id` serait signé comme un lot
        d'événements.
        """
        if request.path.rstrip("/").endswith("/machine/logs"):
            # Journal du SDK : canonique `project_id|sdk-logs|issued_at`.
            return f"{project.id}|sdk-logs|{data['issued_at']}"
        if data.get("session_id"):
            # Envoi d'événements : canonique `project_id|session_id|issued_at`.
            return f"{project.id}|{data['session_id']}|{data['issued_at']}"
        if data.get("exam_id") is not None and data.get("student_id") is not None:
            # Création de session : canonique figée par 01_BACKEND.md §4.1.
            return build_session_canonical_string(
                str(project.id), str(data["exam_id"]), str(data["student_id"]), int(data["issued_at"])
            )
        return None

    @staticmethod
    def _enforce_rate_limit(project: Project):
        """Limite grossière du débit par projet via le cache (01_BACKEND.md §12).

        Pourquoi un compteur en cache plutôt que `django-ratelimit` : les vues DRF machine ne
        portent pas de `request.user`, ce qui complique l'usage du décorateur standard. Un
        compteur par fenêtre glissante de 60 s suffit à freiner une boucle d'un SDK buggé.
        Valeur volontairement large (prototype) : à calibrer.
        """
        limit = settings.MACHINE_RATE_LIMIT_PER_MINUTE
        key = f"machine:rl:{project.id}"
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=60)
            count = 1
        if count > limit:
            raise AuthenticationFailed("Trop de requêtes pour ce projet (rate limit).")


class IsHMACAuthenticated(BasePermission):
    """Permission : n'autorise que les requêtes dont `request.auth` est un projet signé."""

    def has_permission(self, request, view):
        return isinstance(getattr(request, "auth", None), AuthenticatedProject)
