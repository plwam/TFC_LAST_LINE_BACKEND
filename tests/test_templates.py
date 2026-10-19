"""Rendu des templates (06_FRONTEND_GUIDE.md) : chaque page clé répond 200 et affiche les bons
éléments. Ces tests attrapent les régressions d'intégration entre vue ↔ contexte ↔ template
(balises manquantes, variables non transmises, fuite de secret dans le HTML).
"""

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from html import unescape

from apps.events.models import Event

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Coquille commune (base.html)
# ---------------------------------------------------------------------------


def test_base_shell_tailwind_cdn_and_pinned_version(client):
    html = client.get(reverse("account_login")).content.decode()
    # Tailwind via CDN, version ÉPINGLÉE (06 §2.3) — aucune feuille de style maison.
    assert "https://cdn.tailwindcss.com/3.4.17" in html
    # Le CSS écrit à la main a été supprimé : aucune référence ne doit subsister.
    assert "custom.css" not in html
    assert 'lang="fr"' in html
    # Jeton CSRF disponible pour les appels fetch POST (06 §10).
    assert 'name="csrf-token"' in html
    # Lien d'évitement d'accessibilité.
    assert "Aller au contenu principal" in html


def test_login_page_renders(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "EvaSee" in html
    assert "Connexion" in html or "connecter" in html.lower()


# ---------------------------------------------------------------------------
# Page d'accueil publique + liens connexion ↔ inscription
# ---------------------------------------------------------------------------


def test_landing_page_public_renders(client):
    response = client.get(reverse("root"))
    assert response.status_code == 200
    html = response.content.decode()
    # Présentation du service + appels à l'action vers connexion et inscription.
    assert "Surveillez vos évaluations en ligne" in html
    assert reverse("account_login") in html
    assert reverse("account_signup") in html
    # Pas de redirection : la vitrine est accessible sans compte.
    assert "Risque élevé" in html


def test_landing_redirects_authenticated_user(client, developer):
    client.force_login(developer.user)
    response = client.get(reverse("root"))
    assert response.status_code == 302
    assert response["Location"] == reverse("dashboard:home")


def test_login_page_has_clear_signup_link(client):
    html = client.get(reverse("account_login")).content.decode()
    assert reverse("account_signup") in html
    assert "Pas encore de compte" in html
    assert "Créer un compte" in html


def test_signup_page_has_login_link(client):
    html = client.get(reverse("account_signup")).content.decode()
    assert reverse("account_login") in html
    assert "Se connecter" in html



# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_home_renders(client, developer, project):
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Bonjour" in html
    assert "Projets" in html
    assert "Sessions actives" in html
    assert "Alertes à examiner" in html


def test_project_list_renders_projects(client, developer, project):
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:project-list"))
    html = response.content.decode()
    assert response.status_code == 200
    assert project.name in html
    assert "Nouveau projet" in html


@pytest.mark.parametrize("tab", ["overview", "keys", "sessions", "logs", "integration", "settings"])
def test_project_detail_all_tabs_render(client, developer, project, tab):
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:project-detail", args=[project.id]), {"tab": tab})
    assert response.status_code == 200


def test_project_keys_tab_shows_public_and_masked_secret(client, developer, project):
    client.force_login(developer.user)
    html = client.get(
        reverse("dashboard:project-detail", args=[project.id]), {"tab": "keys"}
    ).content.decode()
    assert project.public_key in html
    assert "sk_live_••••" in html
    assert project.secret_last4 in html
    # Le secret EN CLAIR ne doit JAMAIS apparaître dans le HTML initial (UC-3).
    assert str(project.secret_key) not in html


def test_project_integration_tab_uses_sdk_cdn_url(client, developer, project):
    client.force_login(developer.user)
    html = client.get(
        reverse("dashboard:project-detail", args=[project.id]), {"tab": "integration"}
    ).content.decode()
    assert settings.SDK_CDN_URL in html


def test_project_create_form_renders(client, developer):
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:project-create"))
    assert response.status_code == 200
    html = response.content.decode()
    assert 'name="name"' in html
    assert 'name="site_url"' in html


def test_project_list_exposes_lifecycle_actions_with_confirmation(client, developer, project):
    client.force_login(developer.user)
    html = client.get(reverse("dashboard:project-list")).content.decode()
    # La fenêtre d'alerte partagée est présente dans la coquille.
    assert 'id="confirm-action-dialog"' in html
    # Les actions dangereuses sont câblées au dialogue de confirmation.
    assert reverse("dashboard:project-suspend", args=[project.id]) in html
    assert reverse("dashboard:project-disable", args=[project.id]) in html
    assert "data-confirm-title=" in html
    # Garde-fou : un commentaire `{# … #}` multi-lignes n'est PAS un commentaire Django et
    # s'afficherait en clair — on vérifie qu'aucun texte de commentaire ne fuit dans la page.
    assert "Fenêtre d'alerte générique" not in html


def test_project_overview_shows_lifecycle_actions(client, developer, project):
    client.force_login(developer.user)
    html = client.get(
        reverse("dashboard:project-detail", args=[project.id]), {"tab": "overview"}
    ).content.decode()
    assert "Cycle de vie" in html
    assert reverse("dashboard:project-suspend", args=[project.id]) in html
    assert reverse("dashboard:project-disable", args=[project.id]) in html
    assert "data-confirm-title=" in html


def test_project_overview_shows_identity_and_integration_keys(client, developer, project):
    """La vue d'ensemble expose les métadonnées du projet et la clé publique, sans le secret."""
    client.force_login(developer.user)
    html = client.get(
        reverse("dashboard:project-detail", args=[project.id]), {"tab": "overview"}
    ).content.decode()
    assert "Domaine surveillé" in html
    assert "Dernière modification" in html
    # Clé publique et identifiant copiables ; le secret ne doit JAMAIS apparaître (UC-3).
    assert project.public_key in html
    assert str(project.id) in html
    assert str(project.secret_key) not in html


def test_project_detail_delete_requires_confirmation(client, developer, project):
    client.force_login(developer.user)
    html = client.get(reverse("dashboard:project-detail", args=[project.id])).content.decode()
    assert "data-confirm-link" in html


def test_project_delete_confirm_renders(client, developer, project):
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:project-delete", args=[project.id]))
    assert response.status_code == 200
    assert project.name in response.content.decode()


def test_flash_message_rendered_after_create(client, developer):
    client.force_login(developer.user)
    response = client.post(
        reverse("dashboard:project-create"),
        {"name": "Projet Flash", "description": "", "site_url": "https://flash.edu"},
        follow=True,
    )
    assert response.status_code == 200
    assert "Projet créé" in response.content.decode()


def test_docs_page_developer_sees_only_integration_endpoints(client, developer):
    """Un développeur ne voit que les endpoints d'intégration de sa plateforme (LMS / SDK)."""
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:docs"))
    assert response.status_code == 200
    html = response.content.decode()
    # Surfaces d'intégration : API machine (SDK / LMS).
    assert "/api/v1/machine/sessions/" in html
    assert "/api/v1/machine/events/" in html
    assert "/api/v1/machine/logs/" in html
    # Les surfaces de gestion (API JWT) et d'exploitation (API publique, réservée à
    # l'extension du propriétaire) sont MASQUÉES pour un simple développeur.
    assert "/api/v1/auth/token/" not in html
    assert "/api/v1/projects/" not in html
    assert "/api/v1/sessions/" not in html
    assert "/public/registered-hosts/" not in html
    assert "/public/health/" not in html
    # Chaque bloc de code porte un bouton copier (icône + coche de confirmation).
    assert "data-copy-code-target" in html
    assert "data-copy-check" in html
    # Liens vers les interfaces générées (Swagger UI et ReDoc).
    assert reverse("docs:swagger") in html
    assert reverse("docs:redoc") in html


def test_docs_page_superuser_sees_all_endpoints(client, django_user_model):
    """Le superutilisateur (propriétaire du système) voit toutes les surfaces."""
    superuser = django_user_model.objects.create_superuser(
        username="root", email="root@example.com", password="motdepasse"
    )
    client.force_login(superuser)
    response = client.get(reverse("dashboard:docs"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "/api/v1/machine/sessions/" in html
    assert "/public/registered-hosts/" in html
    # En plus : les surfaces de gestion réservées au propriétaire.
    assert "/api/v1/auth/token/" in html
    assert "/api/v1/projects/" in html
    assert "/api/v1/sessions/" in html


def test_openapi_docs_require_login(client):
    """Swagger/ReDoc/schéma ne sont pas publics : un anonyme est redirigé vers la connexion."""
    for name in ("docs:schema", "docs:swagger", "docs:redoc"):
        response = client.get(reverse(name))
        assert response.status_code in (301, 302, 303)
        assert reverse("account_login") in response["Location"]


def test_openapi_docs_accessible_when_logged_in(client, developer):
    client.force_login(developer.user)
    for name in ("docs:schema", "docs:swagger", "docs:redoc"):
        assert client.get(reverse(name)).status_code == 200


def test_account_page_renders(client, developer):
    client.force_login(developer.user)
    response = client.get(reverse("dashboard:account"))
    assert response.status_code == 200
    assert "full_name" in response.content.decode()


# ---------------------------------------------------------------------------
# Détail session (chronologie)
# ---------------------------------------------------------------------------


def _session_with_events(client, developer, session, make_event):
    make_event(
        session,
        event_id="crit",
        event_type=Event.Type.AUTOMATION_DETECTED,
        occurred_at=timezone.now(),
    )
    make_event(
        session,
        event_id="soft",
        event_type=Event.Type.FOCUS_LOST,
        occurred_at=timezone.now(),
    )
    client.force_login(developer.user)
    return client.get(reverse("dashboard:session-detail", args=[session.id]))


def test_session_detail_renders_chronology(client, developer, session, make_event):
    response = _session_with_events(client, developer, session, make_event)
    # `unescape` : Django échappe les apostrophes en `&#x27;` dans le texte — on compare au
    # texte réel, pas à la représentation HTML échappée.
    text = unescape(response.content.decode())
    assert response.status_code == 200
    assert session.exam_id in text
    # Phrases du presenter présentes (contrat type technique → phrase française).
    assert "Navigateur piloté par un script d'automatisation." in text
    assert "La fenêtre d'examen a perdu le focus." in text
    # Un événement critique porte la bordure rouge (06 §8.8).
    assert "border-red-500" in text


def test_session_detail_summary_counts_events(client, developer, session, make_event):
    response = _session_with_events(client, developer, session, make_event)
    assert response.status_code == 200
    assert response.context["summary_total"] == 2
    labels = {row["label"] for row in response.context["summary"]}
    assert "Automatisation" in labels
    assert "Perte de focus" in labels


def test_session_detail_critical_filter(client, developer, session, make_event):
    make_event(session, event_id="crit", event_type=Event.Type.AUTOMATION_DETECTED)
    make_event(session, event_id="soft", event_type=Event.Type.FOCUS_LOST)
    client.force_login(developer.user)
    text = unescape(
        client.get(
            reverse("dashboard:session-detail", args=[session.id]), {"critical": "1"}
        ).content.decode()
    )
    assert "Navigateur piloté par un script d'automatisation." in text
    assert "La fenêtre d'examen a perdu le focus." not in text


# ---------------------------------------------------------------------------
# Pages d'erreur
# ---------------------------------------------------------------------------


@override_settings(DEBUG=False)
def test_custom_404_template(client):
    response = client.get("/cette-url-nexiste-pas/")
    assert response.status_code == 404
    assert "404" in response.content.decode()


@override_settings(DEBUG=False)
def test_custom_403_template(client, project):
    from apps.developers.models import Developer

    project.developer.status = Developer.Status.SUSPENDED
    project.developer.save(update_fields=["status"])
    client.force_login(project.developer.user)
    response = client.post(reverse("dashboard:project-reveal-secret", args=[project.id]))
    assert response.status_code == 403
    assert "403" in response.content.decode()
