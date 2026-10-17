"""
Sérialiseurs de l'API JWT (01_BACKEND.md §10).

Règle de sécurité : la clé SECRÈTE n'apparaît JAMAIS dans un sérialiseur. Seule la clé
publique et les 4 derniers caractères de la clé secrète (pour l'affichage masqué) sont exposés.
La révélation de la clé secrète reste une action dédiée et journalisée.
"""

from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.projects.models import Project
from apps.sessions.models import ExamSession


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT dont l'identifiant est l'EMAIL, pas le username.

    Pourquoi un sérialiseur dédié : le `User` hérite d'`AbstractUser` (champ `username`), mais
    la plateforme s'authentifie par email (`ACCOUNT_LOGIN_METHODS = {'email'}`). Le
    `TokenObtainPairSerializer` par défaut interroge le backend Django avec `username`, ce qui
    échouerait ici. On authentifie donc explicitement par email (insensible à la casse).
    """

    # On remplace le champ `username` par `email` dans le formulaire (et donc l'OpenAPI).
    email = serializers.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop(self.username_field, None)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        from apps.accounts.models import User

        user = User.objects.filter(email__iexact=email).first()
        # Message volontairement identique dans tous les cas d'échec : on ne révèle pas si
        # l'email existe (énumération de comptes).
        if user is None or not user.check_password(password) or not user.is_active:
            raise AuthenticationFailed("Identifiants invalides.")
        refresh = self.get_token(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


class ProjectSerializer(serializers.ModelSerializer):
    """Projet exposé à son propriétaire. `secret_key` volontairement ABSENTE."""

    masked_secret = serializers.CharField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "site_url",
            "public_key",
            "masked_secret",
            "status",
            "is_archived",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "public_key",
            "masked_secret",
            "status",
            "is_archived",
            "created_at",
            "updated_at",
        ]


class ExamSessionSerializer(serializers.ModelSerializer):
    """Session d'examen exposée en lecture seule (mêmes données que l'onglet Sessions)."""

    duration_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = ExamSession
        fields = [
            "id",
            "project",
            "exam_id",
            "student_id",
            "status",
            "risk_score",
            "started_at",
            "ended_at",
            "duration_seconds",
        ]
        read_only_fields = fields
