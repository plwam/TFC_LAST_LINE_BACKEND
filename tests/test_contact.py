"""Formulaire de contact de la page d'accueil : envoi vers l'équipe + anti-robot."""

import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

# En dev, EMAIL_BACKEND est la console (pas de `mail.outbox`) : on bascule sur le backend
# mémoire pour inspecter les messages envoyés.
locmem = override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")

VALID_PAYLOAD = {
    "name": "Ada Lovelace",
    "email": "ada@exemple.com",
    "subject": "Intégration LMS",
    "message": "Bonjour, nous souhaitons brancher EvaSee sur Moodle.",
    "company": "",  # pot de miel vide = humain
}


def test_landing_exposes_contact_section_and_form(client):
    html = client.get(reverse("root")).content.decode()
    assert 'id="contact"' in html
    for field in ("name", "email", "subject", "message"):
        assert f'name="{field}"' in html
    assert "csrfmiddlewaretoken" in html


@locmem
def test_contact_post_sends_email_to_team(client, settings):
    mail.outbox.clear()
    response = client.post(reverse("root"), VALID_PAYLOAD)

    assert response.status_code == 302
    assert response["Location"] == reverse("root") + "#contact"
    assert len(mail.outbox) == 1

    sent = mail.outbox[0]
    assert sent.to == [settings.CONTACT_EMAIL]
    assert sent.reply_to == ["ada@exemple.com"]
    assert "[EvaSee · Contact]" in sent.subject
    assert "Moodle" in sent.body
    assert "ada@exemple.com" in sent.body


@locmem
def test_contact_success_message_displayed_after_redirect(client):
    response = client.post(reverse("root"), VALID_PAYLOAD, follow=True)
    assert response.status_code == 200
    assert "Votre message a bien été transmis" in response.content.decode()


@locmem
def test_contact_post_invalid_shows_errors_without_sending(client):
    mail.outbox.clear()
    response = client.post(reverse("root"), {**VALID_PAYLOAD, "email": "pas-un-email"})

    assert response.status_code == 200
    assert len(mail.outbox) == 0
    assert "Saisissez une adresse e-mail valide" in response.content.decode()


@locmem
def test_contact_honeypot_silently_drops_robot(client):
    mail.outbox.clear()
    response = client.post(reverse("root"), {**VALID_PAYLOAD, "company": "spam-bot"})

    # On répond « succès » au robot pour ne pas l'inciter à réessayer, sans rien envoyer.
    assert response.status_code == 302
    assert response["Location"] == reverse("root") + "#contact"
    assert len(mail.outbox) == 0
