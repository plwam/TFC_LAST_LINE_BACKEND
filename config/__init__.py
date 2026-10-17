"""Initialisation du package `config`.

Pourquoi ce fichier : lorsque la base de production est MySQL (01_BACKEND.md §3), Django
attend le module `MySQLdb` (mysqlclient, une extension C). On utilise à la place PyMySQL,
une implémentation 100 % Python, pour éviter d'avoir à compiler mysqlclient sous Windows.
`install_as_MySQLdb()` rend PyMySQL importable sous le nom `MySQLdb`, ce qui satisfait Django
sans changer la configuration `DATABASES`.

En développement (SQLite), cet import est inoffensif : il n'établit aucune connexion.
"""

try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # PyMySQL absent (ex. environnement réduit) : sans effet en SQLite.
    pass


# Expose l'application Celery sous `config.celery_app` pour que les décorateurs
# `@shared_task` des apps soient rattachés à la bonne application dès l'import de Django.
try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except Exception:  # pragma: no cover — au cas où Celery n'est pas encore installé/lancé.
    pass
