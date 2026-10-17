"""
Signaux django-allauth — création automatique du profil `Developer`.

Point d'intégration critique (01_BACKEND.md §4) : quel que soit le mode d'inscription
(email/mot de passe OU Google/GitHub), un `User` doit recevoir un profil `Developer`.
Sans ce signal, un développeur inscrit via GitHub se retrouverait avec un `User` sans
profil, cassant l'accès au dashboard et l'isolation multi-tenant.
"""

from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from .models import Developer


@receiver(user_signed_up)
def create_developer_profile(request, user, **kwargs):
    """Crée le profil Developer au moment exact de l'inscription.

    `get_or_create` plutôt que `create` : certains flux (reconnexion d'un compte social
    déjà existant) peuvent rejouer ce signal — on ne veut pas lever d'erreur d'unicité.
    Exemple : login GitHub sur un email déjà inscrit par mot de passe → le profil existe
    déjà, `get_or_create` le renvoie tel quel.
    """
    Developer.objects.get_or_create(
        user=user,
        defaults={
            "full_name": user.get_full_name() or user.email,
            "status": Developer.Status.PENDING,
        },
    )
