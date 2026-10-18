"""Comportement de la case « Se souvenir de moi » sur la page de connexion (UC-1).

Vérifie que la case est bien rendue et qu'elle pilote la durée de vie de la session :
- cochée  → cookie de session PERSISTANT (expire dans `SESSION_COOKIE_AGE`, 2 semaines) ;
- décochée → cookie de session DE SESSION (effacé à la fermeture du navigateur).
"""

import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _verify(dev):
    EmailAddress.objects.create(
        user=dev.user, email=dev.user.email, verified=True, primary=True
    )


def test_login_page_renders_remember_checkbox(client):
    html = client.get(reverse("account_login")).content.decode()
    assert 'name="remember"' in html


def test_remember_checked_persists_session(client, make_developer):
    dev = make_developer("remember-on@example.com")
    _verify(dev)

    response = client.post(
        reverse("account_login"),
        {"login": dev.user.email, "password": "pw12345!", "remember": "on"},
    )

    assert response.status_code == 302
    cookie = response.cookies.get("sessionid")
    assert cookie is not None
    # Un cookie persistant porte une date d'expiration explicite.
    assert cookie.get("expires")


def test_remember_unchecked_is_browser_close_session(client, make_developer):
    dev = make_developer("remember-off@example.com")
    _verify(dev)

    response = client.post(
        reverse("account_login"),
        {"login": dev.user.email, "password": "pw12345!"},
    )

    assert response.status_code == 302
    cookie = response.cookies.get("sessionid")
    assert cookie is not None
    # Cookie de session : ni date d'expiration, ni max-age.
    assert not cookie.get("expires")
    assert not cookie.get("max-age")
