"""
Modèle utilisateur — architecture « identité générique + profils par rôle » (01_BACKEND.md §3).

`User` ne porte AUCUNE logique métier de rôle : c'est uniquement l'identité d'authentification
(qui peut se connecter). Les rôles (Developer, Administrator, futurs autres) sont des modèles
séparés liés en OneToOne, ce qui permet d'ajouter un nouveau type d'utilisateur sans toucher ici.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """AUTH_USER_MODEL. Consommé nativement par django-allauth sans adaptation.

    - `email` devient unique et sert d'identifiant de connexion (ACCOUNT_LOGIN_METHODS={'email'}).
    - `username` est conservé (hérité) : allauth le renseigne automatiquement à l'inscription
      via l'adaptateur par défaut, ce qui évite de rompre la compatibilité de l'app `account`.
    """

    email = models.EmailField(unique=True, verbose_name="adresse email")

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return self.email

    @property
    def display_name(self):
        """Nom à afficher dans l'interface : profil développeur si présent, sinon email.

        Exemple : un compte connecté via GitHub a un `full_name` renseigné → on l'affiche ;
        un compte sans profil (cas théorique) retombe proprement sur l'email, sans planter.
        """
        developer = getattr(self, "developer_profile", None)
        if developer and developer.full_name:
            return developer.full_name
        return self.get_full_name() or self.email
