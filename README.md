# ExamSDK — Backend

Backend Django de la plateforme **ExamSDK** : un SaaS de surveillance d'examens en ligne.

Le même projet Django sert à la fois :

- le **tableau de bord développeur** (templates rendus côté serveur, session Django) ;
- l'**API machine** consommée par le SDK de surveillance et un éventuel LMS (signature HMAC) ;
- une **API JWT** destinée à de futurs clients non-navigateur (mobile, desktop) ;
- une **API publique** sans authentification (extension navigateur, monitoring) ;
- l'**administration** du service via le Django Admin natif.

> Ce README décrit l'installation, le lancement et la structure du dépôt. Les décisions de
> conception détaillées sont consignées dans les documents listés en fin de fichier
> (`01_BACKEND.md`, `SETUP.md`, `06_FRONTEND_GUIDE.md`, …).

---

## Sommaire

- [Stack technique](#stack-technique)
- [Surfaces et authentification](#surfaces-et-authentification)
- [Démarrage rapide](#démarrage-rapide)
- [Configuration (`.env`)](#configuration-env)
- [URLs principales](#urls-principales)
- [Documentation des endpoints](#documentation-des-endpoints)
- [Tests](#tests)
- [Structure du projet](#structure-du-projet)
- [Documentation du projet](#documentation-du-projet)

---

## Stack technique

| Technologie | Rôle |
| --- | --- |
| Django 5.2 | Framework : templates du dashboard **et** API (via DRF) depuis un seul projet |
| Django REST Framework | Sérialiseurs, permissions, viewsets pour toutes les API |
| django-allauth | Authentification humaine : email/mot de passe + OAuth Google / GitHub |
| djangorestframework-simplejwt | Jetons JWT (API développeur) |
| drf-spectacular | Schéma OpenAPI (Swagger UI / ReDoc), versions épinglées |
| Celery + Redis | Tâches asynchrones (score de risque) ; Redis optionnel en dev |
| MySQL 8+ (prod) / SQLite (dev) | Base de données |
| Tailwind CSS (CDN épinglé) | Interface, sans feuille de style maison |
| Pygments | Coloration syntaxique **côté serveur** des blocs de code |

---

## Surfaces et authentification

Trois mécanismes distincts — **à ne jamais confondre**.

| Surface | Préfixe | Qui l'utilise | Authentification |
| --- | --- | --- | --- |
| Tableau de bord web | `/dashboard/` | Développeur / admin humain | Session Django (cookies) |
| API JSON développeur | `/api/v1/` | Futurs clients mobile / desktop | JWT (`Authorization: Bearer`) |
| API machine | `/api/v1/machine/` | SDK, LMS | HMAC (en-têtes signés) |
| API publique | `/public/` | Extension navigateur, monitoring | Aucune |
| Administration | `/admin/` | Staff | Session + `is_staff` |

La logique métier vit dans une couche de **services partagés** (`apps/*/services.py`), appelée
par les vues templates **et** par les vues DRF, afin de ne jamais dupliquer de règle métier.

---

## Démarrage rapide

Environnement de référence : **Python 3.10**, Windows / PowerShell. Un environnement virtuel
local au projet est obligatoire (voir [Configuration](#configuration-env)).

```powershell
# 1. Environnement virtuel
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt

# 2. Configuration (copier l'exemple, puis ajuster si besoin)
Copy-Item .env.example .env

# 3. Base de données
.\.venv\Scripts\python manage.py migrate

# 4. Compte d'administration
.\.venv\Scripts\python manage.py createsuperuser

# 5. Serveur de développement
.\.venv\Scripts\python manage.py runserver
```

Le site est ensuite disponible sur <http://127.0.0.1:8000/> :

- `/` — landing publique (redirige vers le dashboard si connecté) ;
- `/accounts/` — connexion / inscription / réinitialisation ;
- `/dashboard/` — tableau de bord développeur ;
- `/admin/` — administration ;
- `/dashboard/docs/` — documentation des endpoints (voir plus bas).

---

## Configuration (`.env`)

Le fichier `.env` n'est **jamais** versionné (voir `.gitignore`). Copier `.env.example` et
remplacer les valeurs. Variables principales :

| Variable | Rôle | Défaut / remarque |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | Settings actifs | `config.settings.dev` |
| `DJANGO_SECRET_KEY` | Clé Django | À changer en production |
| `DEBUG` | Mode debug | `True` en dev |
| `DATABASE_URL` | Base de données | Vide = SQLite ; prod = `mysql://...` |
| `REDIS_URL` | Cache + broker Celery | Vide = cache mémoire + Celery synchrone |
| `FIELD_ENCRYPTION_KEY` | Chiffrement Fernet des `secret_key` | **Ne jamais régénérer en production** |
| `JWT_SIGNING_KEY` | Signature des JWT développeur | — |
| `MACHINE_RATE_LIMIT_PER_MINUTE` | Plafond de requêtes HMAC par projet | `600` |
| `SDK_CDN_URL` | URL du SDK affichée dans l'onglet Intégration | — |
| `GOOGLE_/GITHUB_OAUTH_*` | Providers allauth | Vide = bouton masqué |

Générer une clé de chiffrement :

```powershell
.\.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Détails complets : [`SETUP.md`](SETUP.md) §2.

---

## URLs principales

| URL | Description |
| --- | --- |
| `/` | Landing publique |
| `/accounts/` | Connexion / inscription / reset (allauth) |
| `/dashboard/` | Tableau de bord développeur |
| `/dashboard/docs/` | Référence des endpoints, intégrée au dashboard |
| `/admin/` | Django Admin ; `/admin/metrics/` = tableau de bord de métriques (UC-13) |
| `/api/v1/` | API JWT (projets, sessions) |
| `/api/v1/machine/` | API machine (SDK / LMS), authentification HMAC |
| `/public/` | API publique (`registered-hosts/`, `health/`) |
| `/docs/swagger/`, `/docs/redoc/` | Interfaces OpenAPI générées |
| `/docs/schema/` | Schéma OpenAPI brut |
| `/health/` et `/public/health/` | Sondes de monitoring |

---

## Documentation des endpoints

Deux niveaux, complémentaires :

1. **Page maison `/dashboard/docs/`** — documentation intégrée au dashboard, rendue côté
   serveur (code coloré par Pygments, aucun CDN requis), avec un exemple de requête et de
   réponse par endpoint et un bouton « copier » par bloc de code. Elle ne couvre **que** les
   endpoints HTTP (API JWT, API machine HMAC, API publique) ; la documentation du SDK viendra
   ultérieurement.
2. **Interfaces générées** — `/docs/swagger/` (Swagger UI) et `/docs/redoc/` (ReDoc), pilotées
   par le schéma OpenAPI de drf-spectacular. Les **versions des moteurs sont épinglées** dans
   `SPECTACULAR_SETTINGS` (`config/settings/base.py`) : une montée de version majeure de ces
   bibliothèques (`redoc@latest` → v3) peut casser le rendu des pages.

### Endpoints machine (HMAC)

| Méthode | Endpoint | Rôle |
| --- | --- | --- |
| `POST` | `/api/v1/machine/sessions/` | Ouvre une session (idempotent) |
| `POST` | `/api/v1/machine/sessions/{id}/close/` | Clôture (`invalid: true` → « Invalide ») |
| `POST` | `/api/v1/machine/events/` | Ingestion d'un lot d'événements (idempotent par `event_id`) |
| `GET` | `/api/v1/machine/events/` | Consultation (filtres `exam_id`, `student_id`, `type`) |

En-têtes signés `X-ExamSDK-Public-Key` et `X-ExamSDK-Signature` (HMAC-SHA256 hexadécimal).
Chaînes canoniques : `project_id|exam_id|student_id|issued_at` (création de session) et
`project_id|session_id|issued_at` (événements, clôture).

---

## Tests

```powershell
.\.venv\Scripts\python -m pytest
```

87 tests couvrant l'isolation multi-tenant, la suspension de compte, le contrat HMAC,
l'immuabilité des événements, le score de risque, l'API publique, le rendu des templates,
l'admin et la validation des formulaires. Le détail figure dans [`SETUP.md`](SETUP.md) §11.

Vérifications statiques :

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py makemigrations --check --dry-run
```

> Utiliser impérativement le venv `.venv` : le Python global de la machine embarque une version
> de `django-allauth` incompatible avec Django 5.2.

---

## Structure du projet

```text
backend/
├── config/                 # Projet Django
│   ├── settings/           # base.py, dev.py, prod.py (séparation par environnement)
│   └── urls.py             # Routage racine : séparation stricte entre surfaces
├── apps/                   # Applications métier
│   ├── accounts/           # User (identité d'authentification générique)
│   ├── developers/         # Developer (profil métier développeur, statut)
│   ├── administration/     # Administrator + vue de métriques admin
│   ├── projects/           # Project (clés API) + services métier
│   ├── sessions/           # ExamSession + calcul du score de risque (Celery)
│   ├── events/             # Event (immuable) + catalogue des types
│   ├── dashboard/          # Tableau de bord développeur (vues + templates)
│   ├── api/                # API JWT (projets, sessions) + schéma OpenAPI
│   ├── machine_api/        # API machine HMAC (SDK / LMS)
│   ├── public/             # API publique (hôtes autorisés, health)
│   ├── audit/              # AccessLog (journal des actions sensibles)
│   └── core/               # SiteBranding, landing, helpers HMAC, filtres de code
├── templates/              # Gabarits de base, composants, pages allauth, erreurs
├── static/js/dashboard.js  # JavaScript applicatif (vanilla, sans dépendance)
├── tests/                  # Suite pytest
├── manage.py
├── requirements.txt
├── pytest.ini
└── .env.example
```

---

## Documentation du projet

| Fichier | Contenu |
| --- | --- |
| [`01_BACKEND.md`](01_BACKEND.md) | Spécification d'implémentation du backend |
| [`SETUP.md`](SETUP.md) | Installation, configuration, pièges connus, surfaces API |
| [`06_FRONTEND_GUIDE.md`](06_FRONTEND_GUIDE.md) | Guide du tableau de bord et des templates |
| [`05_AGENT_GUIDELINES.md`](05_AGENT_GUIDELINES.md) | Règles de contribution et décisions |
| [`A_FAIRE_SDK.md`](A_FAIRE_SDK.md) | Travaux restants côté SDK |
