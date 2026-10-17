"""
Admin de l'identité visuelle du site (logo, nom).

Affiché comme un objet unique : la liste redirige directement vers le formulaire de l'unique
entrée, et l'action « ajouter » disparaît dès qu'elle existe (singleton, cf. models.SiteBranding).
"""

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from apps.core.models import SiteBranding


@admin.register(SiteBranding)
class SiteBrandingAdmin(admin.ModelAdmin):
    list_display = ("site_name", "logo_preview", "updated_at")
    readonly_fields = ("logo_preview", "updated_at")
    fields = ("site_name", "logo", "logo_preview", "updated_at")

    @admin.display(description="Aperçu")
    def logo_preview(self, obj):
        if not obj or not obj.logo:
            return "—"
        # Sert le média via MEDIA_URL (développement) ; en production le serveur web s'en charge.
        return format_html(
            '<img src="{}" alt="Logo" style="height:40px;background:#fff;padding:4px;border-radius:4px" />',
            obj.logo.url,
        )

    def has_add_permission(self, request):
        # Une seule identité : plus d'ajout possible une fois l'entrée créée.
        return not SiteBranding.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # On ne supprime pas l'identité (on la modifie) : évite un site sans logo par accident.
        return False

    def changelist_view(self, request, extra_context=None):
        # La « liste » n'a aucun sens pour un singleton : on ouvre directement le formulaire.
        obj = SiteBranding.objects.first()
        if obj is not None:
            url = reverse("admin:core_sitebranding_change", args=[obj.pk])
            return HttpResponseRedirect(url)
        return super().changelist_view(request, extra_context=extra_context)
