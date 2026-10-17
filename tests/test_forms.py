"""Tests de validation du formulaire projet (site_url).

Régression : un `site_url` sans schéma (« localhost:3000 ») doit être accepté et normalisé
en http:// en développement, mais refusé en production (06_FRONTEND_GUIDE.md §8.5).
"""

import pytest
from django.test import override_settings

from apps.dashboard.forms import ProjectForm


def _form(site_url):
    return ProjectForm(
        data={"name": "Projet test", "description": "", "site_url": site_url}
    )


@override_settings(DEBUG=True)
def test_site_url_without_scheme_is_accepted_and_normalised():
    form = _form("localhost:3000")
    assert form.is_valid(), form.errors
    assert form.cleaned_data["site_url"] == "http://localhost:3000"


def test_site_url_bare_domain_gets_http_scheme():
    form = _form("examens.mon-universite.edu")
    assert form.is_valid(), form.errors
    assert form.cleaned_data["site_url"] == "http://examens.mon-universite.edu"


def test_site_url_with_scheme_is_preserved():
    form = _form("https://examens.mon-universite.edu")
    assert form.is_valid(), form.errors
    assert form.cleaned_data["site_url"] == "https://examens.mon-universite.edu"


@override_settings(DEBUG=False)
def test_localhost_rejected_in_production():
    form = _form("localhost:3000")
    assert not form.is_valid()
    assert "site_url" in form.errors


@override_settings(DEBUG=False)
def test_ip_literal_rejected_in_production():
    form = _form("http://127.0.0.1:8000")
    assert not form.is_valid()
    assert "site_url" in form.errors


def test_empty_site_url_rejected():
    form = _form("   ")
    assert not form.is_valid()
    assert "site_url" in form.errors


def test_unsupported_scheme_rejected():
    form = _form("ftp://examens.mon-universite.edu")
    assert not form.is_valid()
    assert "site_url" in form.errors
