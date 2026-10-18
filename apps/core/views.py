"""
Vues transverses du noyau.
"""

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from apps.core.forms import ContactForm


class LandingView(TemplateView):
    """Page d'accueil PUBLIQUE `/` — présentation du service (06_FRONTEND_GUIDE.md §8.1).

    Comportement :
    - visiteur anonyme → la page marketing décrit EvaSee et propose de se connecter/créer un
      compte (modèle des plateformes « fournisseur d'API ») ;
    - utilisateur authentifié → redirection immédiate vers `/dashboard/` (il n'a pas besoin de
      revoir la vitrine).

    La page porte aussi le FORMULAIRE DE CONTACT (section `#contact`) : un POST valide envoie un
    e-mail à l'équipe (réglage `CONTACT_EMAIL`) puis redirige vers l'ancre de la section.

    Note (point à valider) : la spec §8.1 décrivait la racine comme une simple redirection
    « connecté → dashboard, sinon → login ». On choisit ici une vraie page publique, demandée
    explicitement ; c'est un écart mineur et assumé.
    """

    template_name = "landing.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs.setdefault("contact_form", ContactForm())
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = ContactForm(request.POST)
        if form.is_valid():
            # Un pot de miel rempli = robot : on n'envoie rien, mais on ne le signale pas.
            if not form.is_spam():
                form.send()
            messages.success(
                request,
                _("Merci ! Votre message a bien été transmis à l'équipe EvaSee."),
            )
            return HttpResponseRedirect(reverse("root") + "#contact")
        return self.render_to_response(self.get_context_data(contact_form=form))
