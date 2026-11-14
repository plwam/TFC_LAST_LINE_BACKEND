"""Force brute des clés de signature JWT (RFC 7518 §3.2, 01_BACKEND.md §14).

Le JWT développeur est signé en HMAC-SHA256 (`rest_framework_simplejwt`). La RFC 7518 impose
un minimum de 32 octets de clé pour SHA-256 : en dessous, PyJWT émet `InsecureKeyLengthWarning`
et la résistance théorique à la force brute chute. Ce test fait échouer la CI plutôt que de
laisser un avertissement passer inaperçu (fail fast) — une clé trop courte dans un `.env`
mal recopié est précisément le genre d'erreur que personne ne remarque.
"""

from django.conf import settings

import pytest


def test_jwt_signing_key_is_at_least_32_bytes():
    """`JWT_SIGNING_KEY` (HMAC-SHA256) doit faire >= 32 octets, conformément à la RFC 7518 §3.2."""
    assert isinstance(settings.JWT_SIGNING_KEY, str)
    assert len(settings.JWT_SIGNING_KEY.encode("utf-8")) >= 32, (
        "`JWT_SIGNING_KEY` est trop courte (< 32 octets, minimum RFC 7518 §3.2 pour HMAC-SHA256). "
        "Allongez la variable d'environnement — ne la tronquez JAMAIS en production."
    )
