"""Sérialiseurs de l'API machine HMAC (01_BACKEND.md §9).

Ces sérialiseurs valident les DONNÉES ; la signature, elle, est vérifiée en amont par
`HMACAuthentication`. Aucune donnée de `metadata` n'est interprétée (elle reste brute).
"""

from rest_framework import serializers

from apps.events.models import Event


class SessionCreateSerializer(serializers.Serializer):
    """Corps de `POST /api/v1/machine/sessions/` (hors champs de signature)."""

    exam_id = serializers.CharField(max_length=255)
    student_id = serializers.CharField(max_length=255)
    sdk_version = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    # Horodatage de début (epoch secondes, optionnel : par défaut, l'heure serveur).
    started_at = serializers.DateTimeField(required=False)


class SessionCloseSerializer(serializers.Serializer):
    """Corps de `POST /api/v1/machine/sessions/{id}/close/`."""

    # Un LMS peut clore une session comme « invalide » (ex. fraude avérée).
    invalid = serializers.BooleanField(required=False, default=False)


class EventIngestSerializer(serializers.Serializer):
    """Un événement du lot. Les champs de `metadata` ne sont pas validés en profondeur : ils
    proviennent d'un navigateur et ne doivent jamais déclencher d'erreur serveur (§9 défensif)."""

    event_id = serializers.CharField(max_length=128)
    type = serializers.ChoiceField(choices=Event.Type.choices)
    source = serializers.ChoiceField(choices=Event.Source.choices, default=Event.Source.SDK)
    confidence_score = serializers.FloatField(required=False, allow_null=True)
    sdk_version = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    user_agent = serializers.CharField(required=False, allow_blank=True, default="")
    integrity_hash = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, default=dict)
    occurred_at = serializers.DateTimeField()


class EventBatchSerializer(serializers.Serializer):
    """Lot d'événements envoyé par le SDK/extension (d'un seul envoi réseau)."""

    events = EventIngestSerializer(many=True)


class EventReadSerializer(serializers.ModelSerializer):
    """Représentation d'un événement pour `GET /api/v1/machine/events/` (lecture)."""

    class Meta:
        model = Event
        fields = [
            "id",
            "event_id",
            "type",
            "source",
            "confidence_score",
            "sdk_version",
            "integrity_hash",
            "metadata",
            "occurred_at",
        ]
