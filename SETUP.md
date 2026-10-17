# SETUP — ExamSDK backend

Guide d'installation et de configuration du backend Django. Toute décision de
configuration non évidente est expliquée ici (exigence `05_AGENT_GUIDELINES.md`).

## 1. Environnement

- Python 3.10 (testé sur 3.10.11), Windows/PowerShell.
- Un environnement virtuel **local** au projet est obligatoire : la version
  globale de `django-allauth` (0.57) est **incompatible avec Django 5.2**.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## 2. Configuration (`.env`)

1. Copier `.env.example` en `.env` à la racine de `backend/`.
2. Le fichier `.env` n'est **jamais** versionné (voir `.gitignore`).

Variables principales :

| Variable | Rôle | Défaut / remarque |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | Settings actifs | `config.settings.dev` |
| `DJANGO_SECRET_KEY` | Clé Django | À changer en prod |
| `DEBUG` | Mode debug | `True` en dev |
| `DATABASE_URL` | Base de données | Vide = SQLite (`db.sqlite3`) ; prod = `mysql://...` |
| `REDIS_URL` | Cache + broker Celery | Vide = cache mémoire + Celery eager |
| `FIELD_ENCRYPTION_KEY` | Chiffrement Fernet des `secret_key` | **Ne jamais régénérer en prod** |
| `JWT_SIGNING_KEY` | Signature JWT développeur | — |
| `MACHINE_RATE_LIMIT_PER_MINUTE` | Plafond de requêtes HMAC par projet (anti-boucle SDK) | `600` |
| `SDK_CDN_URL` | URL du SDK affichée dans l'onglet Intégration | — |
| `GOOGLE_/GITHUB_OAUTH_*` | Providers allauth | Vide = bouton masqué |

Générer une clé de chiffrement :

```powershell
.\.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 3. Base de données et migrations

```powershell
.\.venv\Scripts\python manage.py migrate
```

- **Dev** : SQLite, aucun service externe requis.
- **Prod** : MySQL via `DATABASE_URL`. Le driver est **PyMySQL** (pur Python)
  pour éviter la compilation C de `mysqlclient` sous Windows ; `config/__init__.py`
  appelle `pymysql.install_as_MySQLdb()` au démarrage.

## 4. Lancer le serveur

```powershell
.\.venv\Scripts\python manage.py runserver
```

- `/` : **landing publique** (présentation du service). Connecté → redirige vers `/dashboard/`.
  Écart assumé à `06_FRONTEND_GUIDE.md` §8.1 (demande utilisateur) : voir §5.
- `/accounts/` : login / signup / reset (django-allauth).
- `/admin/` : Django Admin (superutilisateur uniquement) — voir §9.
- `/media/` : fichiers téléversés (logo) — servis par Django en dev uniquement (voir §12).

Créer un compte de test :

```powershell
.\.venv\Scripts\python manage.py createsuperuser
```

## 5. Frontend

- **Tailwind CSS uniquement, via le CDN** (`https://cdn.tailwindcss.com/3.4.17`,
  version épinglée). Aucun fichier CSS "écrit à la main" n'est utilisé : les
  composants réutilisables vivent dans `templates/components/` et les classes
  proviennent exclusivement de Tailwind (`06_FRONTEND_GUIDE.md`).
- Le thème (piles de polices système) est défini dans le
  `<script>tailwind.config = {...}</script>` de `templates/base.html`, **après**
  le script CDN. La palette de référence est `g` (gris « console ») : fonds
  `g-950/900/850/800`, bordures `g-700/600`, textes `g-text/g-muted/g-faint`,
  accent bleu `g-blue/g-accent`. Une palette `brand` (indigo) subsiste pour
  compatibilité mais n'est plus utilisée par les pages.
- **Thème sombre GLOBAL (écart assumé à `06_FRONTEND_GUIDE.md` §6, demande
  utilisateur)** : la palette « console » s'applique **partout**, pas seulement au
  dashboard — landing publique, pages allauth (connexion/inscription), pages
  d'erreur `403/404/500` et docs. `templates/base.html` impose le fond sombre
  (`bg-g-950`) et `dashboard/base_dashboard.html` en hérite. La landing
  (`templates/landing.html`) reprend la mise en page de `tailwindcss.com` :
  barre de navigation translucide collante, grand titre `tracking-tighter`, bloc
  de code, grille de fonctionnalités, pied de page en colonnes. Les pages
  d'erreur étant autonomes (sans `{% extends %}`), elles embarquent une copie
  minimale de la palette dans leur propre `tailwind.config`.
  - `components/alert.html` expose un paramètre `theme` (`dark` par défaut,
    désormais toujours utilisé) ;
  - formulaires : `TailwindFormMixin` et `DarkFormMixin` (`apps/core/forms.py`)
    posent les **mêmes** classes sombres ; tous les formulaires (dashboard **et**
    allauth via `ACCOUNT_FORMS`) sont donc sombres et cohérents.
- **Coloration syntaxique des blocs de code** (demande utilisateur : « comme dans un
  éditeur »), faite **côté serveur** via le filtre `highlight` de
  `apps/core/templatetags/code_extras.py` ([Pygments](https://pygments.org/), déjà
  présent dans l'environnement). Pygments est configuré en `noclasses=True` : il pose la
  couleur dans un attribut `style` **en ligne**, donc **aucune feuille de style ni script
  tiers** n'est chargé et le rendu en couleurs est **garanti partout et hors-ligne**.
  Usage : `{% load code_extras %}` puis
  `<pre><code>{% filter highlight:"python" %}…{% endfilter %}</code></pre>`
  (onglet Intégration d'un projet, landing). Si Pygments ou le langage est indisponible,
  le texte est simplement échappé (jamais d'erreur, jamais de code exécuté). Le cadre
  « fenêtre d'éditeur » (points rouge/jaune/vert + nom de fichier) est du Tailwind pur.
  - *Historique* : une première version s'appuyait sur highlight.js en CDN + thème
    `github-dark.min.css` ; le rendu n'était pas fiable (CSS tiers bloqué/non appliqué),
    d'où le passage au rendu serveur.
- Le JavaScript applicatif (`static/js/dashboard.js`) reste du vanilla JS, **sans aucune
  dépendance externe** (ni npm, ni bundler, ni CDN au runtime).
- **Validation du `site_url`** (`apps/dashboard/forms.py::ProjectForm`) : le champ est déclaré
  en `CharField` (et non le `URLField` du modèle) pour **tolérer une saisie sans schéma** —
  « `localhost:3000` » ou « `examens.mon-universite.edu` » sont acceptés et normalisés en
  `http://…` (valeur stockée avec schéma). Les adresses `localhost` / IP littérales sont
  autorisées **en développement** (`DEBUG=True`) mais refusées en production.

## 6. Redis / Celery (optionnel en dev)

`redis-server` n'étant pas installé sur la machine de développement, l'absence
de `REDIS_URL` bascule automatiquement :

- le cache sur un `LocMemCache` en mémoire,
- Celery en exécution **synchrone** (`CELERY_TASK_ALWAYS_EAGER`), ce qui permet
  de développer le score de risque en continu sans Redis.

**Non retenu pour l'instant : Docker.** Aucune image Docker n'est construite ni
installée (décision de projet) : la pile se lance directement avec `runserver` et,
si besoin, `celery -A config worker` + un Redis local. Un `Dockerfile`/`docker-compose`
pourra être ajouté plus tard sans changer le code applicatif.

Pour utiliser Redis localement : renseigner `REDIS_URL` dans `.env` puis lancer
un worker `celery -A config worker -l info`.

## 7. Vérifications

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py makemigrations --check --dry-run
```

### Pièges connus
- `{# ... #}` ne commente **qu'une seule ligne** en Django. Tout commentaire
  multi-lignes doit utiliser `{% comment %}...{% endcomment %}`.
- L'app `django.contrib.sessions` occupe déjà le label `sessions` : l'app métier
  `apps/sessions` déclare donc le `app_label` **`examsessions`** (tables `examsessions_*`).
- Les providers OAuth d'allauth exigent le paquet `requests`.
- `django-celery-results` doit être dans `INSTALLED_APPS` pour consulter les
  résultats de tâches depuis l'admin.

## 8. Surfaces API (étape 2)

| Préfixe | Surface | Authentification |
| --- | --- | --- |
| `/api/v1/` | API JWT (projets, sessions) | JWT (`Authorization: Bearer`) |
| `/api/v1/machine/` | API machine (SDK / LMS) | HMAC (en-têtes signés) |
| `/public/` | API publique (extension) | aucune |
| `/docs/swagger/`, `/docs/redoc/` | Documentation OpenAPI | aucune |
| `/health/` et `/public/health/` | Sonde de monitoring | aucune |

### Endpoints machine (HMAC)

- `POST /api/v1/machine/sessions/` (UC-5) — ouvre une session (idempotent).
- `POST /api/v1/machine/sessions/{id}/close/` (UC-7) — clôt (`invalid: true` → « Invalide »).
- `POST /api/v1/machine/events/` (UC-10) — ingestion d'un lot d'événements (idempotent par `event_id`).
- `GET /api/v1/machine/events/?exam_id=&type=&student_id=` (UC-6) — consultation.

**Contrat HMAC (⚠ à confirmer avec `02_SDK.md` §14).** En-têtes `X-ExamSDK-Public-Key` et
`X-ExamSDK-Signature` (HMAC-SHA256 hex). La chaîne canonique de **création de session** est
figée par `01_BACKEND.md` §4.1 : `project_id|exam_id|student_id|issued_at`. Celle des
**événements** n'est pas spécifiée dans les documents accessibles : elle est définie ici comme
`project_id|session_id|issued_at`. À valider avant l'écriture du SDK.

### Immutabilité des événements

`Event.save()` refuse toute mise à jour et `Event.delete()` est bloqué (BNF-33). En production
MySQL, on révoque en plus le privilège `DELETE` sur la table `events` (défense en profondeur).
La purge (rétention) relèvera d'une tâche de maintenance privilégiée, jamais de l'interface.

## 9. Django Admin (UC-11 → UC-13)

L'admin natif est utilisé, sans template custom (une seule exception, la vue de métriques).

| Modèle | Particularité |
| --- | --- |
| `Developer` | Actions en masse **Valider** / **Suspendre** (UC-12) — chaque action écrit une entrée `AccessLog`. Liste affiche l'`email` (porté par `User`). |
| `Administrator` | Gestion des rôles `superadmin` / `moderator` (UC-11). |
| `AccessLog` | **Lecture seule** (aucun ajout/modification) ; filtres action / acteur / date, `date_hierarchy`. |
| `Project` | `secret_key` **exclue** du formulaire : même l'admin ne la voit pas en clair. |
| `ExamSession` | Consultation ; `risk_score` en lecture seule. |
| `Event` | **Lecture seule stricte** (ni ajout, ni modification, ni suppression) — immuabilité, BNF-33. |

Vue de métriques (UC-13) : **`/admin/metrics/`** (réservé au staff). Compteurs agrégés
développeurs par statut, projets actifs/archivés, sessions actives / à risque ≥ seuil élevé,
événements critiques. Aucune donnée personnelle étudiante.

En-tête : le site s'affiche « ExamSDK — Administration » (`config/urls.py`).

## 10. Score de risque (Celery)

- Formule : `apps/sessions/risk.py` — somme pondérée (poids par catégorie × confiance, renforcée
  pour les types critiques) passée par une saturation `1 - e^-x`, résultat borné `[0,1]`
  (`BF-16`). C'est un **indicateur d'aide à la décision**, pas une preuve.
- Tâche : `apps/sessions/tasks.py::compute_risk_score_task`, déclenchée **après ingestion**
  d'événements (`POST /api/v1/machine/events/`) via `.delay()`. Jamais dans le chemin de la
  réponse HTTP ; en dev sans Redis, l'exécution est synchrone (`CELERY_TASK_ALWAYS_EAGER`).
- Seuils d'interprétation : `RISK_THRESHOLDS = {"medium": 0.3, "high": 0.6}` (`config/settings/base.py`).
  Valeurs indicatives, à calibrer après mesures réelles (Chapitre 3) — **point à valider**.
- Les **types critiques** (bordure rouge + pondération renforcée) sont centralisés dans
  `apps/events/catalog.py` (partagé par l'affichage et le score), **point à valider**.

## 11. Tests

```powershell
.\.venv\Scripts\python -m pytest          # 86 tests
.\.venv\Scripts\python -m pytest tests/test_machine_api.py -v
```

`pytest.ini` force `DJANGO_SETTINGS_MODULE=config.settings.dev`. Couverture :

- `test_tenant_isolation.py` — isolation multi-tenant (404 cross-tenant, manager scopé).
- `test_suspension.py` — lecture autorisée / écriture refusée (403) pour un compte suspendu.
- `test_projects_api.py` — JWT par email, reveal `no-store` + audit, régénération, secret
  chiffré au repos (jamais exposé en série).
- `test_machine_api.py` — HMAC : signature, fraîcheur, clé inconnue, projet archivé, idempotence,
  scoping des événements, clôture.
- `test_events.py` — immuabilité (update/delete interdits), unicité `(session, event_id)`.
- `test_presenters.py` — parité 27 types, formatage FR, défensivité, échappement XSS.
- `test_risk_score.py` — bornes, monotonie, impact de la confiance, tâche Celery.
- `test_public.py` — hôtes autorisés, exclusion des archivés, minimisation (aucune clé/ID).
- `test_templates.py` — **rendu des templates** : chaque page clé répond 200, Tailwind CDN
  épinglé (pas de CSS maison), absence du secret en clair dans le HTML, phrases de la chronologie,
  filtres, pages 403/404 personnalisées.
- `test_admin.py` — accès staff, actions de modération journalisées, admin événements en lecture
  seule, vue de métriques.
- `test_forms.py` — validation du `site_url` : tolérance sans schéma, normalisation `http://`,
  refus de `localhost`/IP hors `DEBUG` (pytest force `DEBUG=False`, d'où `override_settings`).

> **Important** : utiliser le venv `.venv` (Django 5.2 / allauth 65). Le Python global de la
> machine embarque une `django-allauth` 0.57 incompatible (`requirements.txt` exige `>=65,<66`).

## 12. Identité visuelle (logo éditable)

Le logo et le nom du site sont modifiables **sans redéploiement**, depuis le Django Admin :

- Modèle `apps.core.models.SiteBranding` — **singleton** (`save()` force `pk=1` ; l'admin
  redirige la liste vers le formulaire unique et masque « ajouter » dès que l'entrée existe).
  Champs : `site_name` (défaut `ExamSDK`) et `logo` (`FileField`, formats SVG/PNG/JPEG/WebP/GIF).
  On utilise un `FileField` (pas `ImageField`) pour **ne pas exiger Pillow** et accepter le SVG.
- Exposé à **tous** les templates par le context processor
  `apps.core.context_processors.site_branding` (`{{ site_branding }}`) : landing, pages allauth,
  sidebar du dashboard. Si aucun logo n'est défini, le nom du site s'affiche à la place.
- **Médias** : `MEDIA_URL = "media/"`, `MEDIA_ROOT = backend/media` ; servis par Django
  uniquement en dev (`config/urls.py`, via `static(...)` actif seulement si `DEBUG`). En
  production, c'est le rôle du serveur web (Whitenoise ne sert **que** le statique).

```powershell
# Depuis le navigateur : /admin/ → « Identité visuelle du site » → téléverser le logo.
```
