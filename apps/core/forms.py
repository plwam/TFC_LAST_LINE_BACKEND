"""Formulaires transverses — briques réutilisables par plusieurs apps (dashboard, accounts)."""

from django import forms


class TailwindFormMixin:
    """Applique les classes Tailwind à tous les widgets d'un formulaire.

    Pourquoi un mixin plutôt que django-widget-tweaks : cette librairie n'est pas dans le
    périmètre validé (05_AGENT_GUIDELINES §3) et le besoin se résout en quelques lignes.
    Utilisé aussi bien par les formulaires du dashboard que par les formulaires allauth
    (via ACCOUNT_FORMS), pour une apparence cohérente de tous les champs.

    Les classes posées ici sont celles du thème SOMBRE « console », désormais appliqué à toute
    l'application (landing, connexion, tableau de bord) — voir SETUP.md §6. Un seul jeu de
    classes à faire évoluer pour re-thématiser l'ensemble des formulaires.
    """

    INPUT_CLASSES = (
        "block w-full rounded-md border border-g-600 bg-g-800 px-3 py-2 text-sm text-g-text "
        "placeholder:text-g-faint shadow-sm focus:border-g-blue focus:outline-none "
        "focus:ring-2 focus:ring-g-accent/40"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            # Les cases à cocher / listes radio ont un style différent : on ne leur applique
            # pas les classes de champ texte.
            if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                existing = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{existing} {self.INPUT_CLASSES}".strip()
            # Accessibilité (06_FRONTEND_GUIDE.md §12) : on annonce l'état invalide et on relie
            # le champ à son message d'erreur pour les lecteurs d'écran (uniquement quand une
            # erreur existe, donc sur un formulaire déjà lié/validé).
            if self.is_bound and self.errors.get(name):
                field.widget.attrs["aria-invalid"] = "true"
                field.widget.attrs["aria-describedby"] = f"{field.widget.attrs.get('id', 'id_' + name)}-error"


class DarkFormMixin(TailwindFormMixin):
    """Alias sémantique de `TailwindFormMixin` pour les formulaires du dashboard.

    Historiquement distinct (public clair / console sombre) ; depuis que l'application entière
    suit le thème sombre, les deux mixins posent exactement les mêmes classes. Conservé pour la
    lisibilité des formulaires du dashboard (`ProjectForm`, `AccountForm`, `ConfirmByNameForm`).
    """
