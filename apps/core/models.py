"""
Identité visuelle du site (logo, nom) — briques transverses (apps.core).

Le logo est modifiable SANS redéploiement : il est téléversé depuis le Django Admin et lu par
les templates via le context processor `apps.core.context_processors.site_branding`.

Modèle « singleton » volontaire (pk toujours = 1) : il n'existe qu'une seule identité de site,
la contrainte est posée dans `save()` et dans l'admin (`has_add_permission`), pas dans le schéma
(une contrainte de ligne unique serait propre à un SGBD donné).
"""

from django.core.validators import FileExtensionValidator
from django.db import models

# Formats acceptés pour le logo : SVG et WebP en plus des formats bitmap courants. On valide
# l'extension (pas le contenu) — cela évite d'exiger Pillow, absent des dépendances du projet
# (cf. requirements.txt) alors qu'un logo est souvent un simple SVG.
LOGO_EXTENSIONS = ["svg", "png", "jpg", "jpeg", "webp", "gif"]


class SiteBranding(models.Model):
    site_name = models.CharField(
        max_length=60,
        default="EvaSee",
        help_text="Nom affiché à côté du logo (et utilisé si aucun logo n'est fourni).",
    )
    logo = models.FileField(
        upload_to="branding/",
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=LOGO_EXTENSIONS)],
        help_text="Formats acceptés : SVG, PNG, JPEG, WebP, GIF. Laissez vide pour le nom seul.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "identité visuelle du site"
        verbose_name_plural = "identité visuelle du site"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        # Force la clé primaire à 1 : garantit l'unicité de l'instance (singleton applicatif).
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        """Renvoie l'identité visuelle, ou un objet non enregistré avec les valeurs par défaut.

        On ne crée PAS l'enregistrement ici : la lecture ne doit pas écrire en base, et les
        pages publiques (landing, connexion) ne doivent pas échouer si la table est vide.
        """
        return cls.objects.first() or cls()
