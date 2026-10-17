"""
Middleware d'audit — journalise les consultations de ressources sensibles (BNF-33).

Pourquoi un middleware plutôt qu'un appel dans chaque vue : la règle du projet est que la
trace de consultation ne doit jamais dépendre de la discipline du développeur qui écrit la vue
(06_FRONTEND_GUIDE.md §8.6.3). Une table déclarative associe un nom de vue à un type de
ressource ; le middleware s'occupe du reste.

Limites volontaires :
- uniquement les GET réussis (200) d'un utilisateur authentifié ;
- uniquement les vues listées (évite un journal noyé par le bruit des pages sans enjeu,
  ex. la page d'accueil ou la liste complète des projets).
"""

from apps.audit.models import AccessLog

# Vue (par nom d'URL) → type de ressource consultée.
AUDITED_VIEWS = {
    "dashboard:project-detail": "Project",
    "dashboard:session-detail": "ExamSession",
}


class AccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._record_consultation(request, response)
        return response

    def _record_consultation(self, request, response):
        if request.method != "GET" or response.status_code != 200:
            return

        match = getattr(request, "resolver_match", None)
        if not match or not match.view_name:
            return

        resource_type = AUDITED_VIEWS.get(match.view_name)
        if not resource_type:
            return

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return

        developer = getattr(user, "developer_profile", None)
        # L'identifiant de ressource est le kwargs d'URL quand il existe (ex. <uuid>).
        resource_id = ""
        for key in ("pk", "project_id", "session_id", "uuid"):
            if key in match.kwargs:
                resource_id = str(match.kwargs[key])
                break

        AccessLog.record(
            action=AccessLog.Action.CONSULTATION,
            actor=user,
            developer=developer,
            resource_type=resource_type,
            resource_id=resource_id,
            request=request,
        )
