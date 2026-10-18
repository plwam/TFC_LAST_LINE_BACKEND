"""Formulaires transverses — briques réutilisables par plusieurs apps (dashboard, accounts)."""

from django import forms
from django.conf import settings
from django.core.mail import EmailMessage


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


# Classes des champs du formulaire de contact : rendu « console » futuriste (fond translucide,
# liseré lumineux au focus) distinct des champs de formulaire standards.
CONTACT_FIELD_CLASSES = (
    "w-full rounded-lg border border-g-700 bg-g-950/70 px-4 py-3 text-sm text-g-text "
    "placeholder:text-g-faint transition focus:border-[#5fd0ff] focus:outline-none "
    "focus:ring-2 focus:ring-[#5fd0ff]/40"
)


class ContactForm(forms.Form):
    """Formulaire de contact public (page d'accueil) → e-mail à l'équipe EvaSee.

    Protections : champs bornés + « pot de miel » (`company`) rempli uniquement par les robots.
    L'envoi passe par le backend e-mail configuré (`EMAIL_BACKEND`) : console en développement,
    SMTP en production.
    """

    name = forms.CharField(
        label="Nom",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Votre nom", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "vous@exemple.com", "autocomplete": "email"}),
    )
    subject = forms.CharField(
        label="Sujet",
        max_length=160,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Intégration, question technique…"}),
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Décrivez votre besoin…"}),
    )
    # Champ invisible pour un humain ; un robot le remplit souvent. S'il est rempli, on
    # n'envoie rien tout en répondant « succès » (on ne renseigne pas le robot).
    company = forms.CharField(
        label="Société",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {CONTACT_FIELD_CLASSES}".strip()

    def is_spam(self):
        return bool(self.cleaned_data.get("company"))

    def send(self):
        subject = (self.cleaned_data.get("subject") or "").strip() or "Nouveau message"
        body = (
            "Nouveau message depuis la page d'accueil EvaSee\n\n"
            f"Nom    : {self.cleaned_data['name']}\n"
            f"E-mail : {self.cleaned_data['email']}\n"
            f"Sujet  : {subject}\n\n"
            f"{self.cleaned_data['message']}\n"
        )
        email = EmailMessage(
            subject=f"[EvaSee · Contact] {subject}",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.CONTACT_EMAIL],
            reply_to=[self.cleaned_data["email"]],
        )
        email.send(fail_silently=False)

