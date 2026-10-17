"""
Mixins de protection des vues du dashboard (01_BACKEND.md §12, 06_FRONTEND_GUIDE.md §7).

Règle : toute vue du dashboard exige une session authentifiée ET un profil `Developer`. Les
vues d'écriture refusent en plus les comptes `suspended` (403) — le masquage des boutons côté
template n'est qu'un confort visuel, la seule protection fiable est côté serveur.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


class DeveloperRequiredMixin(LoginRequiredMixin):
    """Session obligatoire + présence d'un profil Developer.

    Un `User` sans profil Developer (cas théorique : futur rôle non-développeur) ne doit jamais
    provoquer une 500. On le redirige proprement vers la connexion avec un message clair.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self._developer(request) is None:
            messages.error(
                request,
                "Votre compte n'est pas rattaché à un espace développeur.",
            )
            return redirect("account_login")
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _developer(request):
        # `getattr(..., None)` est volontaire : l'accès à un OneToOne absent lève
        # RelatedObjectDoesNotExist, qui hérite d'AttributeError → getattr renvoie None.
        return getattr(request.user, "developer_profile", None)


class WritableDeveloperRequiredMixin(DeveloperRequiredMixin):
    """Pour les actions d'écriture / sensibles : refuse les comptes suspendus (403).

    Exemple : un compte `suspended` qui POSTerait directement sur
    `/dashboard/projects/<uuid>/regenerate-secret/` reçoit 403, même si le bouton est masqué
    dans l'interface. Les comptes `pending` restent autorisés (ils peuvent préparer leurs projets).
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            developer = self._developer(request)
            if developer is not None and developer.is_suspended:
                raise PermissionDenied("Compte suspendu : action non autorisée.")
        return super().dispatch(request, *args, **kwargs)
