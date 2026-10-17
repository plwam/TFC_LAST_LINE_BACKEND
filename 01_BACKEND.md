# Backend SaaS — Spécification d'implémentation complète

> **Prérequis de lecture :** `00_PROJECT_OVERVIEW.md`. Ce document remplace toute version antérieure — il intègre le fait que le backend Django **sert lui-même** le tableau de bord développeur (templates rendus côté serveur), en plus de son API machine (SDK/LMS) et d'une API JWT prévue pour de futurs clients (app mobile/desktop).

---

## 0. Rappel de coexistence avec les autres modules

| Module tiers | Point de contact | Document de référence |
| :--- | :--- | :--- |
| **SDK** | Consomme l'API HMAC (`/api/v1/sessions/`, `/api/v1/events/`) | `02_SDK.md` §14 |
| **Extension** | Consomme l'API publique `/public/registered-hosts/`, sans authentification | `03_EXTENSION.md` §5 |
| **Tests** | Fichiers miroirs attendus | `04_TESTS.md` §2 |

---

## 1. Architecture d'authentification — trois mécanismes distincts, à ne jamais confondre

C'est le point le plus important de ce document à bien assimiler avant de coder quoi que ce soit : le backend expose **trois surfaces**, chacune avec son propre mode d'authentification. Les mélanger serait une erreur de sécurité.

| Surface | Qui l'utilise | Mécanisme | Pourquoi |
| :--- | :--- | :--- | :--- |
| **Tableau de bord web** | Développeur/Admin humain, dans un navigateur | **Sessions Django** (cookies) + `django-allauth` | Rendu serveur classique (templates) — le navigateur gère déjà les cookies de session nativement, pas besoin de JWT ici |
| **API JSON développeur** | Futurs clients non-navigateur (app mobile/desktop, intégrations tierces) | **JWT** (`djangorestframework-simplejwt`) | Prévu dès maintenant même sans client mobile immédiat — évite une réécriture d'architecture plus tard |
| **API machine** | SDK (page d'examen), LMS du développeur | **HMAC** (token de session signé) | Zero Trust — aucune notion d'utilisateur connecté, juste une signature cryptographique vérifiable |

**Règle de conception centrale** : la logique métier (créer un projet, régénérer une clé, consulter des événements) vit dans une **couche de service partagée** (`apps/*/services.py`), appelée à la fois par les vues Django (templates) et par les vues DRF (API JWT) — pour ne jamais dupliquer la logique entre les deux surfaces humaines. Voir §7.

---

## 2. Stack technique et justifications

| Technologie | Rôle | Pourquoi ce choix précis |
| :--- | :--- | :--- |
| **Django 5** | Framework | Sert à la fois les templates du tableau de bord et l'API (via DRF) depuis un seul projet — pas de duplication d'infrastructure. |
| **Django Templates** + Django forms | Tableau de bord développeur | Rendu serveur classique, cohérent avec le choix de ne pas construire de SPA séparée pour le MVP du mémoire. |
| **django-allauth** | Authentification (email/mdp + GitHub + Google) | Gère nativement l'inscription, la connexion, la réinitialisation de mot de passe, et l'authentification sociale (OAuth GitHub/Google) sans réinventer ces flux — BF-01/BF-02. |
| **djangorestframework-simplejwt** | JWT pour la future API mobile/publique | Émission/rafraîchissement de tokens standard, s'intègre nativement à DRF. |
| **Django REST Framework** | Toutes les API (JWT + HMAC) | Sérialiseurs, permissions, viewsets. |
| **MySQL 8+** | Base de données | Cf. section §3, choix déjà validé. |
| **Redis** | Cache + broker Celery | Cache des lectures fréquentes (validation token, liste d'hôtes publique), broker de tâches asynchrones. |
| **Celery** | Tâches async | Score de risque, emails, ne bloquent jamais la réponse HTTP. |
| **drf-spectacular** | Documentation OpenAPI (Swagger/Redoc) | Documente **uniquement** les API JWT et HMAC — pas les vues templates, qui n'ont pas vocation à être consommées par un tiers. |
| **Django Admin natif** (`django.contrib.admin`) | Interface d'administration du service | UC-11 à UC-13 — pas de templates custom à construire, Django Admin est fait exactement pour ce besoin (gestion de modèles, actions en masse, filtres). |

---

## 3. Modèle utilisateur — architecture "identité générique + profils par rôle"

**Décision validée** : `Developer` n'est **pas** le modèle utilisateur Django. On sépare l'**identité** (qui peut se connecter) du **rôle** (ce que cette personne fait sur la plateforme) — pour permettre, comme tu l'as anticipé, l'arrivée future d'autres types d'utilisateurs sans tout restructurer.

```python
# apps/accounts/models.py
class User(AbstractUser):
    """Modèle d'authentification générique — AUTH_USER_MODEL. Ne connaît aucun rôle métier."""
    email = models.EmailField(unique=True)
    # username hérité d'AbstractUser conservé pour compatibilité allauth, email comme identifiant principal

# apps/developers/models.py
class Developer(models.Model):
    """Profil métier, lié 1-à-1 à un User. Un User peut ne PAS avoir de profil Developer (futurs autres rôles)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='developer_profile')
    full_name = models.CharField(max_length=255)
    status = models.CharField(choices=[('pending','pending'),('active','active'),('suspended','suspended')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

# apps/administration/models.py
class Administrator(models.Model):
    """Idem, profil admin. En pratique, ce sont des User avec is_staff=True, utilisables tels quels dans Django Admin."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    role = models.CharField(choices=[('superadmin','superadmin'),('moderator','moderator')])
```

| Pourquoi cette séparation | Bénéfice concret |
| :--- | :--- |
| `User` ne porte aucune logique métier | `django-allauth` fonctionne nativement dessus, sans adaptation |
| `Developer`/`Administrator` sont des profils optionnels | Un futur "Enseignant" ou "Étudiant avec compte" (hors périmètre actuel) s'ajouterait comme un nouveau modèle `OneToOneField(User)`, sans toucher à l'existant |
| Django Admin utilise `User.is_staff`/`is_superuser` nativement | Pas besoin de reconstruire un système de permissions parallèle pour l'admin — on branche `Administrator` dessus en cohérence, pas en substitution |

```python
# settings.py
AUTH_USER_MODEL = 'accounts.User'
```

---

## 4. `django-allauth` — configuration

```python
INSTALLED_APPS += [
    'django.contrib.sites',
    'allauth', 'allauth.account', 'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
]
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
ACCOUNT_LOGIN_METHODS = {'email'}                 # email comme identifiant, pas de username visible
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'           # cohérent avec BF-01 (email valide)
SOCIALACCOUNT_AUTO_SIGNUP = True                   # un login GitHub/Google crée le compte + le profil Developer automatiquement
```

**Point d'intégration important** : un `signal` `allauth` (`user_signed_up`) doit créer automatiquement le profil `Developer` associé, quel que soit le mode d'inscription (email/mdp ou social) — sinon un développeur inscrit via GitHub se retrouverait avec un `User` sans profil `Developer`, cassant tout le reste de l'application.

```python
# apps/developers/signals.py
@receiver(user_signed_up)
def create_developer_profile(request, user, **kwargs):
    Developer.objects.create(user=user, full_name=user.get_full_name() or user.email, status='pending')
```

---

## 5. Modèle de données (reste des classes, inchangé sur le fond)

### 5.1 `Project`
| Champ | Type | Contraintes |
| :--- | :--- | :--- |
| id | UUID | PK |
| developer | FK → Developer | `on_delete=CASCADE` |
| name | CharField | |
| description | TextField | |
| site_url | URLField | alimente la liste blanche de l'extension (`03_EXTENSION.md` §5) |
| public_key | CharField | unique, index |
| secret_key | CharField | chiffrée au repos |
| created_at | DateTimeField | |

### 5.2 `ExamSession`, `Event`, `AccessLog` — inchangés, cf. version précédente de ce document (schéma de données déjà validé, uniquement l'authentification change dans cette révision).

---

## 6. Structure des URLs — séparation stricte templates / API

```python
# config/urls.py
urlpatterns = [
    path('accounts/', include('allauth.urls')),              # login, signup, social, password reset
    path('dashboard/', include('apps.dashboard.urls')),        # TEMPLATES — session auth
    path('admin/', admin.site.urls),                            # Django Admin natif — session auth (is_staff)
    path('api/v1/', include('apps.api.urls')),                  # JWT — pour futurs clients mobile/desktop
    path('api/v1/machine/', include('apps.machine_api.urls')),  # HMAC — SDK/LMS uniquement
    path('public/', include('apps.public.urls')),                # aucune auth (registered-hosts)
    path('docs/', include('apps.api.docs_urls')),                # Swagger/Redoc — documente machine_api + api, pas dashboard
]
```

---

## 7. Couche de service partagée — évite la duplication entre templates et API JWT

```python
# apps/projects/services.py
class ProjectService:
    @staticmethod
    def create_project(developer: Developer, name: str, description: str, site_url: str) -> Project:
        project = Project.objects.create(developer=developer, name=name, description=description, site_url=site_url)
        KeyService.generate_keys(project)          # BF-05, appelé systématiquement
        return project

    @staticmethod
    def regenerate_secret_key(project: Project) -> str:
        # invalide l'ancienne, en génère une nouvelle, log l'action dans AccessLog
        ...
```

```python
# apps/dashboard/views.py (TEMPLATE — utilise le service)
class ProjectCreateView(LoginRequiredMixin, FormView):
    template_name = 'dashboard/project_form.html'
    form_class = ProjectForm
    def form_valid(self, form):
        ProjectService.create_project(self.request.user.developer_profile, **form.cleaned_data)
        return redirect('dashboard:project-list')

# apps/api/views.py (API JWT — utilise LE MÊME service)
class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def perform_create(self, serializer):
        ProjectService.create_project(self.request.user.developer_profile, **serializer.validated_data)
```
**C'est la règle à ne jamais violer** : ni la vue template ni la vue API n'implémentent la logique elles-mêmes — elles appellent toutes les deux `ProjectService`. Un futur bug ou une évolution métier (ex. limiter le nombre de projets par développeur) se corrige à un seul endroit.

---

## 8. Pages du tableau de bord développeur — sections détaillées

**Convention** : chaque page ci-dessous correspond à un template Django (`apps/dashboard/templates/dashboard/*.html`) et une vue basée sur classe (`LoginRequiredMixin` systématique, sauf mention contraire). **Le contenu exact de chaque page, les composants et les technologies d'interface (Tailwind CDN) sont détaillés dans `06_FRONTEND_GUIDE.md`, qui fait foi pour l'UI.**

### 8.1 Pages publiques (non authentifiées, gérées par `allauth`)
- **Connexion** (`/accounts/login/`) — formulaire email/mot de passe + boutons "Continuer avec Google" / "Continuer avec GitHub"
- **Inscription** (`/accounts/signup/`) — idem, formulaire email/mot de passe + boutons sociaux
- **Réinitialisation de mot de passe** — flux standard `allauth` (email → lien → nouveau mot de passe)
- **Vérification d'email** — page intermédiaire obligatoire avant première connexion (`ACCOUNT_EMAIL_VERIFICATION = 'mandatory'`)

### 8.2 `/dashboard/` — Accueil du tableau de bord
- **Section résumé** : nombre total de projets, nombre de sessions actives en ce moment (tous projets confondus), nombre d'événements critiques des dernières 24h
- **Section "Projets récents"** : 3-5 derniers projets créés/modifiés, avec accès rapide
- **Section "Alertes à examiner"** : sessions avec un `risk_score` élevé nécessitant une vérification humaine (BF-16, cohérent avec le modèle hybride IA + validation humaine du Ch.1)

### 8.3 `/dashboard/projects/` — Liste des projets (UC-2)
- **Tableau** : nom, `site_url`, date de création, nombre de sessions actives, statut
- **Action** : bouton "Créer un nouveau projet" → `8.4`
- **Filtre/recherche** par nom

### 8.4 `/dashboard/projects/new/` et `/dashboard/projects/{id}/edit/` — Formulaire projet (UC-2)
- **Champs** : nom, description, `site_url`
- **Validation** : `site_url` doit être une URL valide — message d'erreur explicite sinon (impact direct sur l'extension si mal renseignée)

### 8.5 `/dashboard/projects/{id}/` — Détail d'un projet, organisé en onglets

| Onglet | Contenu |
| :--- | :--- |
| **Vue d'ensemble** | Nom, description, `site_url`, date de création, statistiques d'usage (nb de sessions, nb d'événements sur 30 jours) |
| **Clés API** (UC-3) | `public_key` affichée en clair (copiable) ; `secret_key` masquée par défaut (`sk_live_••••••••1234`), bouton "Révéler" avec confirmation, bouton "Régénérer" avec avertissement explicite (« les sessions signées avec l'ancienne clé cesseront d'être validées ») |
| **Sessions** (UC-6) | Tableau des sessions d'examen : `exam_id`, `student_id`, statut, `risk_score`, date. Filtres par examen/période/étudiant (BF-19). Clic → détail session (§8.6) |
| **Documentation d'intégration** (BF-25) | Extrait de code d'initialisation du SDK pré-rempli avec la `public_key` du projet, lien vers Swagger/Redoc |
| **Paramètres** | Modifier nom/description/`site_url`, zone de danger (supprimer le projet, avec confirmation) |

### 8.6 `/dashboard/sessions/{id}/` — Détail d'une session (UC-6)
- **En-tête** : `exam_id`, `student_id`, statut, `risk_score` mis en évidence visuellement (code couleur selon le niveau)
- **Chronologie des événements** : liste triée par horodatage, chaque événement affiche son `type`, sa `source` (SDK/Extension), son `confidence_score`, et ses métadonnées interprétables (ex. *"Regard détourné pendant 3.4s, angle 32°"* — cf. `02_SDK.md` §9.4)
- **Filtre** par type d'événement

### 8.7 `/dashboard/account/` — Paramètres du compte
- **Profil** : nom complet, email (lecture seule si connecté via social — géré par le fournisseur)
- **Comptes connectés** : liste des fournisseurs sociaux liés (géré par les vues natives `allauth`)
- **Sécurité** : changement de mot de passe (uniquement si compte email/mdp, pas pertinent pour un compte 100% social)
- **Zone de danger** : suppression du compte

### 8.8 Django Admin natif (`/admin/`) — UC-11 à UC-13, pas de template custom
- `DeveloperAdmin` : `list_display = ['email', 'status', 'created_at']`, action en masse "Valider" / "Suspendre" (UC-12)
- `AdministratorAdmin` : gestion des rôles (UC-11)
- `AccessLogAdmin` : lecture seule (`readonly_fields`), filtres par acteur/action/date — consultation d'audit
- Vue custom `/admin/metrics/` (UC-13) : peut rester une vue Django Admin personnalisée (`admin.site.index_template` étendu) plutôt qu'un vrai dashboard séparé, pour rester dans l'esprit "pas de template custom" pour l'admin

---

## 9. API machine (HMAC) — inchangée sur le fond

| Méthode | Endpoint | UC/BF |
| :--- | :--- | :--- |
| POST | `/api/v1/machine/sessions/` | UC-5 |
| POST | `/api/v1/machine/sessions/{id}/close/` | UC-7 |
| POST | `/api/v1/machine/events/` | UC-10 |
| GET | `/api/v1/machine/events/?exam_id=&type=&student_id=` | UC-6 (consommé aussi par le dashboard via le service partagé) |

## 10. API JWT (future) — mêmes capacités que le dashboard, exposées en JSON

| Méthode | Endpoint | Équivalent template |
| :--- | :--- | :--- |
| POST | `/api/v1/auth/token/` | Connexion (obtention JWT) |
| POST | `/api/v1/auth/token/refresh/` | Rafraîchissement |
| GET/POST | `/api/v1/projects/` | §8.3/8.4 |
| POST | `/api/v1/projects/{id}/regenerate-secret/` | §8.5 onglet Clés API |
| GET | `/api/v1/sessions/{id}/` | §8.6 |

## 11. API publique (sans authentification)

| Méthode | Endpoint | Consommateur |
| :--- | :--- | :--- |
| GET | `/public/registered-hosts/` | Extension — `03_EXTENSION.md` §5 |
| GET | `/health/` | Monitoring |

---

## 12. Sécurité — ce qui reste inchangé, ce qui est nouveau

**Inchangé** (déjà validé précédemment) : validation HMAC en temps constant, chiffrement de `secret_key` au repos, isolation multi-tenant par `QuerySet` manager custom, rate limiting par `project_id`, immuabilité de `Event` (applicative + révocation de privilèges MySQL).

**Nouveau, lié à l'authentification humaine** :
- `LoginRequiredMixin` systématique sur toute vue du dashboard — jamais une vue accessible sans vérification explicite.
- Vérification que `request.user` possède bien un `developer_profile` avant d'accéder à toute vue du dashboard (un `User` sans profil `Developer`, cas théorique, ne doit jamais planter avec une 500 mais rediriger proprement).
- CSRF activé nativement par Django sur tous les formulaires templates (comportement par défaut, à ne jamais désactiver).
- Isolation multi-tenant appliquée **aussi** aux vues templates, pas seulement à l'API — un développeur ne doit jamais pouvoir accéder à `/dashboard/projects/{id-d-un-autre-developpeur}/` (vérification `project.developer == request.user.developer_profile` systématique, via le même `TenantScopedManager` que l'API).

---

## 13. Structure de dossier mise à jour

```
backend/
├── config/                      # settings (base/dev/prod), urls.py
├── apps/
│   ├── accounts/                 # User, signals allauth
│   ├── developers/                # Developer, services
│   ├── administration/            # Administrator
│   ├── projects/                  # Project, ProjectService, KeyService
│   ├── sessions/                  # ExamSession
│   ├── events/                    # Event, ingestion, immuabilité
│   ├── audit/                     # AccessLog, middleware
│   ├── dashboard/                  # VUES TEMPLATES — apps/dashboard/templates/dashboard/*.html
│   ├── api/                        # VUES DRF + JWT (futurs clients)
│   ├── machine_api/                # VUES DRF + HMAC (SDK/LMS)
│   ├── public/                     # registered-hosts, health
│   └── core/                       # middleware Zero Trust, HMAC, tenant scoping
├── templates/                       # templates GLOBAUX : base.html, components/, account/, socialaccount/, 403/404/500
│   └── (les templates propres au dashboard vivent dans apps/dashboard/templates/dashboard/, cf. 06_FRONTEND_GUIDE.md §3)
├── static/
├── tests/
└── docker-compose.yml
```

---

## 14. Variables d'environnement (mises à jour)

```
DJANGO_SECRET_KEY=
DATABASE_URL=mysql://...
REDIS_URL=redis://...
FIELD_ENCRYPTION_KEY=
JWT_SIGNING_KEY=
TOKEN_VALIDITY_WINDOW_SECONDS=300
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
EMAIL_BACKEND_URL=
```

---

## 15. Renvoi vers les autres documents

- Contrat d'événement consommé par `/api/v1/machine/events/` → `00_PROJECT_OVERVIEW.md` §7
- Endpoint `/public/registered-hosts/` côté consommateur → `03_EXTENSION.md` §5
- Tests attendus (isolation multi-tenant sur les vues templates ET API, flux allauth) → `04_TESTS.md` §2
