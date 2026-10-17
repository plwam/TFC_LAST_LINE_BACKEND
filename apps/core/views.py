"""
Vues transverses du noyau.
"""

from django.shortcuts import redirect
from django.views.generic import TemplateView


class LandingView(TemplateView):
    """Page d'accueil PUBLIQUE `/` — présentation du service (06_FRONTEND_GUIDE.md §8.1).

    Comportement :
    - visiteur anonyme → la page marketing décrit ExamSDK et propose de se connecter/créer un
      compte (modèle des plateformes « fournisseur d'API ») ;
    - utilisateur authentifié → redirection immédiate vers `/dashboard/` (il n'a pas besoin de
      revoir la vitrine).

    Note (point à valider) : la spec §8.1 décrivait la racine comme une simple redirection
    « connecté → dashboard, sinon → login ». On choisit ici une vraie page publique, demandée
    explicitement ; c'est un écart mineur et assumé.
    """

    template_name = "landing.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)
