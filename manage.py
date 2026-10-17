#!/usr/bin/env python
"""Utilitaire en ligne de commande Django.

Rôle : point d'entrée unique pour `runserver`, `makemigrations`, `migrate`, `test`, etc.
La variable DJANGO_SETTINGS_MODULE est lue depuis l'environnement, avec `config.settings.dev`
par défaut pour ne pas avoir à la préciser à chaque commande en développement local.
"""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django est introuvable. Le venv est-il activé ? "
            "(backend/.venv/Scripts/activate — voir backend/SETUP.md)"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
