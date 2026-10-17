"""
Formulaires du dashboard (06_FRONTEND_GUIDE.md §5.1).

Le mixin `DarkFormMixin` applique les classes Tailwind à tous les widgets texte, ce qui
évite de dépendre de django-widget-tweaks (non validé) pour une dizaine de lignes de code.
"""

from django import forms
from django.conf import settings
from urllib.parse import urlparse

from apps.core.forms import DarkFormMixin
from apps.projects.models import Project


class ProjectForm(DarkFormMixin, forms.ModelForm):
    # Champ déclaré explicitement (CharField plutôt que le `URLField` du modèle) : on veut
    # piloter nous-mêmes la validation pour TOLÉRER une saisie sans schéma (« localhost:3000 »,
    # « examens.edu »). Le `URLField` du modèle rejetait ces saisies avant même notre
    # `clean_site_url` (message « Saisissez une URL valide. »), ce qui bloquait les tests en
    # développement. Le schéma est ajouté automatiquement puis stocké (cf. clean_site_url).
    site_url = forms.CharField(
        label="Adresse du site",
        max_length=500,
        help_text=(
            "Adresse où s'exécute votre plateforme d'examen, ex. https://examens.mon-universite.edu "
            "(« localhost:3000 » accepté en développement)."
        ),
    )

    class Meta:
        model = Project
        fields = ["name", "description", "site_url"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        labels = {
            "name": "Nom du projet",
            "description": "Description",
        }

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Donnez un nom à votre projet.")
        return name

    def clean_site_url(self):
        """Validation du site_url (06_FRONTEND_GUIDE.md §8.5).

        Impact direct : une valeur erronée désactive silencieusement l'extension chez les
        étudiants. On exige donc un schéma http/https et un hôte valide, et on refuse
        localhost / adresses IP littérales hors mode DEBUG (une adresse de dev ne peut pas
        être la cible d'un vrai examen).

        Tolérance de saisie : une adresse sans schéma (« localhost:3000 », « examens.edu »)
        est acceptée et préfixée en http:// ; la valeur normalisée (avec schéma) est stockée.
        """
        raw = (self.cleaned_data.get("site_url") or "").strip()
        if not raw:
            raise forms.ValidationError("Renseignez l'adresse de votre plateforme d'examen.")

        # On distingue « pas de schéma » de « schéma invalide » : sans « :// » on suppose
        # http:// (cas classique d'une adresse de dev saisie à la main).
        candidate = raw if "://" in raw else f"http://{raw}"
        parsed = urlparse(candidate)

        if parsed.scheme not in ("http", "https"):
            raise forms.ValidationError("L'adresse doit commencer par http:// ou https://.")
        if not parsed.hostname:
            raise forms.ValidationError(
                "Saisissez une adresse complète, ex. https://examens.mon-universite.edu"
            )

        host = parsed.hostname.lower()
        if not settings.DEBUG:
            # En production, aucune adresse locale/IP littérale n'est acceptée.
            import ipaddress

            try:
                ipaddress.ip_address(host)
                is_ip = True
            except ValueError:
                is_ip = False
            if host == "localhost" or is_ip:
                raise forms.ValidationError(
                    "Utilisez le nom de domaine public de votre plateforme d'examen."
                )
        return candidate


class AccountForm(DarkFormMixin, forms.Form):
    """Édition du nom complet du développeur (UC-1). L'email n'est pas modifiable ici
    (géré par les vues allauth, cf. 06_FRONTEND_GUIDE.md §8.9)."""

    full_name = forms.CharField(max_length=255, label="Nom complet")

    def clean_full_name(self):
        value = (self.cleaned_data.get("full_name") or "").strip()
        if not value:
            raise forms.ValidationError("Le nom complet est obligatoire.")
        return value


class ConfirmByNameForm(DarkFormMixin, forms.Form):
    """Confirmation d'une action destructive par recopie d'un texte attendu (projet/email).

    Le champ est comparé côté serveur (la comparaison côté JS n'est qu'un confort d'interface).
    """

    confirm = forms.CharField(label="Confirmation", max_length=255)

    def __init__(self, *args, expected_value="", **kwargs):
        self.expected_value = expected_value
        super().__init__(*args, **kwargs)

    def clean_confirm(self):
        value = (self.cleaned_data.get("confirm") or "").strip()
        if value != self.expected_value:
            raise forms.ValidationError("La saisie ne correspond pas.")
        return value
