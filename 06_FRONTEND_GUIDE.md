# Guide Frontend — Tableau de bord développeur (templates Django + Tailwind)

> **Prérequis de lecture :** `05_AGENT_GUIDELINES.md` (règles de travail), `00_PROJECT_OVERVIEW.md`, puis `01_BACKEND.md` (§1 auth, §6 URLs, §7 couche de service, §8 liste des pages). Ce document est la **référence unique de l'interface** : technologies, composants, et contenu exact de chaque page. En cas de divergence avec le §8 de `01_BACKEND.md`, **ce fichier fait foi pour l'UI** ; la logique métier reste dans les services (`apps/*/services.py`).

---

## 0. Périmètre et coexistence

| Dans le périmètre | Hors périmètre (ne pas faire) |
| :--- | :--- |
| Pages rendues côté serveur par Django (templates) pour le **développeur** | Une SPA React/Vue séparée |
| Surcharge de style des pages `django-allauth` (connexion, inscription, etc.) | Page marketing / landing publique |
| Composants réutilisables (boutons, badges, alertes, tableaux, formulaires) | Interface d'administration custom — l'admin reste **Django Admin natif** (UC-11 à UC-13) |
| JavaScript vanilla minimal (copie, révélation de clé, menu mobile, dialogues) | Framework JS (Alpine, HTMX, React…) ou librairie de graphiques **sans validation préalable** (règle n°1 de `05_AGENT_GUIDELINES.md`) |
| Accessibilité WCAG AA, responsive (mobile → desktop) | Mode sombre, multilingue complet (voir §17, points à valider) |

**Coexistence avec les autres modules :**
- **Backend** : chaque page appelle les services de `01_BACKEND.md` §7 ; aucune logique métier dans les templates ni dans le JS.
- **SDK** : l'onglet « Intégration » (§8.6.4) affiche des extraits de code qui doivent rester **strictement alignés** sur `02_SDK.md` §5 (`SdkConfig`) et §17 (`init`).
- **Extension** : le champ `site_url` du formulaire projet alimente `/public/registered-hosts/` (`03_EXTENSION.md` §5) — une valeur erronée désactive silencieusement l'extension chez les étudiants. La validation de ce champ est donc critique (§8.5).
- **Événements** : la chronologie (§8.7) traduit les `EventType` de `00_PROJECT_OVERVIEW.md` §7.1 ; tout nouvel `EventType` impose de mettre à jour le tableau du §9 de ce document.

---

## 1. Stack frontend et justifications

| Technologie | Rôle | Pourquoi ce choix précis |
| :--- | :--- | :--- |
| **Django Templates** (héritage `{% extends %}`, `{% include %}`) | Rendu serveur | Cohérent avec l'architecture validée (`01_BACKEND.md` §1) : le navigateur gère nativement les cookies de session, pas de JWT ni de duplication de logique côté client. |
| **Tailwind CSS via CDN** (Play CDN, **version épinglée**) | Mise en forme | Choix validé pour le prototype : aucun outil de build Node à installer, démarrage immédiat. Limites assumées détaillées au §2.3. |
| **JavaScript vanilla** (`static/js/dashboard.js`) | Interactions | Seules ~5 interactions sont nécessaires (§10). Ajouter un framework pour cela serait disproportionné et hors périmètre. |
| **Élément HTML natif `<dialog>`** | Fenêtres de confirmation | Gestion native du focus, de la touche Échap et de l'accessibilité — aucune librairie de modales à ajouter. |
| **SVG inline** (icônes copiées depuis Heroicons, licence MIT) | Icônes | Aucune requête réseau supplémentaire, aucune dépendance. |
| **Pile de polices système** | Typographie | Aucune police externe : pas de requête tierce, pas de fuite d'adresse IP vers un fournisseur de polices (cohérent avec le discours de minimisation du mémoire). |
| **Framework `messages` de Django** | Retours utilisateur (succès/erreur) | Déjà fourni, s'intègre aux redirections après POST. |
| **Django i18n** (`{% translate %}`) | Textes de l'interface | Intégré à Django (aucune dépendance). Interface en **français**. Voir §17 pour la portée. |

---

## 2. Mise en place de Tailwind via CDN

### 2.1 Bloc `<head>` de `templates/base.html`

```html
<!DOCTYPE html>
<html lang="fr" class="h-full bg-slate-50">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Tableau de bord{% endblock %} — ExamSDK</title>

  {# Jeton CSRF lu par dashboard.js pour les appels fetch POST (voir §10 et §11). #}
  <meta name="csrf-token" content="{{ csrf_token }}">

  {# Tailwind Play CDN — VERSION ÉPINGLÉE (jamais "latest").
     Pourquoi épingler : une mise à jour silencieuse du CDN changerait l'apparence de toute l'application
     sans qu'aucun commit ne l'explique. À l'implémentation, vérifier l'URL exacte et la version courante dans
     la documentation officielle Tailwind (« Play CDN ») avant de figer ce numéro. #}
  <script src="https://cdn.tailwindcss.com/3.4.17"></script>

  {# Configuration du thème : DOIT être placée APRÈS le script CDN, sinon l'objet `tailwind` n'existe pas encore. #}
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            // Couleur de marque unique — modifier ICI uniquement pour re-thématiser tout le tableau de bord.
            brand: { 50: '#eef2ff', 100: '#e0e7ff', 600: '#4f46e5', 700: '#4338ca' },
          },
          fontFamily: {
            // Pile système : aucune police chargée depuis un tiers.
            sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
            mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
          },
        },
      },
    };
  </script>

  {% load static %}
  <link rel="stylesheet" href="{% static 'css/custom.css' %}">  {# styles minimes non exprimables en classes (ex. [hidden]) #}
  {% block extra_head %}{% endblock %}
</head>
<body class="h-full font-sans text-slate-800 antialiased" data-csrf="{{ csrf_token }}">
  <a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">Aller au contenu principal</a>
  {% block body %}{% endblock %}
  <script src="{% static 'js/dashboard.js' %}" defer></script>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

### 2.2 Règle d'écriture des classes (prépare la migration de production)

**Toujours écrire les noms de classes Tailwind en entier, jamais les construire par concaténation.**

```python
# MAUVAIS — avec un build Tailwind compilé, cette classe serait purgée car jamais vue telle quelle dans le code :
badge_class = f"bg-{color}-100 text-{color}-800"

# BON — chaque classe est écrite en toutes lettres, un build futur la détectera sans effort :
RISK_BADGE = {
    "low": "bg-green-100 text-green-800",
    "medium": "bg-amber-100 text-amber-800",
    "high": "bg-red-100 text-red-800",
}
```
Le Play CDN tolérerait la concaténation (il observe le DOM en direct), mais cette tolérance disparaîtra le jour où l'on compilera Tailwind. Respecter cette règle dès maintenant rend la migration triviale.

### 2.3 Limites assumées du Play CDN — à ne pas cacher

| Limite | Conséquence | Mitigation prévue |
| :--- | :--- | :--- |
| La documentation Tailwind indique que le Play CDN est destiné au **développement/prototypage, pas à la production** | Compilation des classes **dans le navigateur de l'utilisateur** : léger coût CPU et poids de script supérieur à un CSS compilé | Acceptable pour le prototype. Voir §2.4 pour la migration |
| Léger « flash » de contenu non stylé au chargement possible | Confort visuel | Garder `custom.css` minimal ; ne pas masquer `<body>` artificiellement |
| Nécessite un accès Internet même en développement local | Impossible de développer hors ligne | Documenter dans `backend/SETUP.md` |
| Pas d'attribut d'intégrité (SRI) possible sur un script généré dynamiquement | Dépendance de confiance envers le CDN | Version épinglée ; pas de Content-Security-Policy stricte tant que le CDN est utilisé (le script de configuration est inline) |
| `@apply` indisponible dans un fichier CSS externe | Pas de classes « composants » dans `custom.css` | Les composants sont des **partials de templates** (§4), pas des classes CSS |

### 2.4 Chemin de migration (à documenter, **ne pas l'implémenter maintenant**)
Remplacer le `<script>` CDN par un fichier CSS compilé avec la CLI autonome de Tailwind (binaire unique, sans Node), générant `static/css/tailwind.css`. Grâce au §2.2, aucun template ne change. Ce passage devient **obligatoire avant toute mise en production réelle** — à rappeler dans `backend/SETUP.md`.

---

## 3. Architecture des templates

```
backend/
├── templates/                            # templates GLOBAUX (hors app)
│   ├── base.html                         # coquille HTML commune (§2.1)
│   ├── 403.html  404.html  500.html      # pages d'erreur (§8.10)
│   ├── components/                       # composants réutilisables (§4)
│   │   ├── button.html  badge_risk.html  badge_status.html  badge_event.html
│   │   ├── alert.html   messages.html    empty_state.html    pagination.html
│   │   ├── form_field.html  copy_field.html  secret_field.html  confirm_dialog.html
│   ├── account/                          # surcharges allauth (§8.2)
│   └── socialaccount/                    # surcharges allauth social (§8.2)
├── apps/dashboard/
│   ├── templates/dashboard/
│   │   ├── base_dashboard.html           # coquille connectée : sidebar + topbar (§6)
│   │   ├── home.html
│   │   ├── project_list.html
│   │   ├── project_form.html
│   │   ├── project_detail.html           # coquille à onglets
│   │   ├── project_tabs/_overview.html  _keys.html  _sessions.html  _integration.html  _settings.html
│   │   ├── project_confirm_delete.html
│   │   ├── session_detail.html
│   │   ├── account.html
│   │   └── account_confirm_delete.html
│   ├── presenters.py                     # EventType → libellé/phrase (§9)
│   ├── context_processors.py             # statut développeur, seuils de risque (§5.2)
│   ├── forms.py                          # TailwindFormMixin + ProjectForm (§5.1)
│   ├── templatetags/dashboard_extras.py  # filtres (risk_level, duration, offset…)
│   └── views.py
└── static/
    ├── css/custom.css
    └── js/dashboard.js
```

> **Alignement avec `01_BACKEND.md` :** le §8 y mentionne `apps/dashboard/templates/dashboard/*.html` et le §13 un dossier `templates/dashboard/`. **Retenir l'arborescence ci-dessus** : templates propres à une app dans l'app, templates transverses (base, composants, allauth, erreurs) dans `templates/`. Mettre à jour le §13 de `01_BACKEND.md` en conséquence.

**Conventions :**
- Un partial dont le nom commence par `_` n'est jamais rendu seul (uniquement via `{% include %}`).
- Blocs exposés par `base_dashboard.html` : `title`, `breadcrumb`, `page_header` (titre + actions), `content`, `extra_js`.
- **Aucune requête ORM dans un template** : les vues préparent tout dans le contexte (évite les N+1 invisibles).
- Tout texte visible est enveloppé dans `{% translate "…" %}` (voir §17).

---

## 4. Système de design et composants

### 4.1 Palette et sémantique des couleurs

| Usage | Classes Tailwind (écrites en entier) |
| :--- | :--- |
| Action principale | `bg-brand-600 hover:bg-brand-700 text-white` |
| Texte principal / secondaire | `text-slate-800` / `text-slate-600` (contraste ≥ 4.5:1 sur fond blanc) |
| Fonds | page `bg-slate-50`, cartes `bg-white` avec `border border-slate-200 rounded-lg shadow-sm` |
| Succès / Avertissement / Danger / Info | `green` / `amber` / `red` / `blue` (fond `-50`, bordure `-200`, texte `-800`) |
| Risque faible / moyen / élevé / non calculé | `green` / `amber` / `red` / `slate` (badges `-100` / texte `-800`) |

**Règle d'accessibilité : la couleur ne porte jamais seule l'information.** Un badge de risque affiche toujours un libellé texte (« Élevé ») en plus de sa couleur.

### 4.2 Composants — spécification

Chaque composant est un partial `components/*.html` appelé par `{% include "components/x.html" with … %}`.

| Composant | Paramètres | Classes de base / comportement |
| :--- | :--- | :--- |
| `button.html` | `label`, `variant` (`primary`/`secondary`/`danger`), `href` ou `type`, `disabled` | Primaire : `inline-flex items-center rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2`. `danger` : même structure en `bg-red-600 hover:bg-red-700`. Si `href` → `<a>`, sinon `<button>` |
| `badge_risk.html` | `score` (float ou `None`) | Niveau via filtre `risk_level` (§5.3). `None` → badge gris « Calcul en cours ». Affiche libellé + pourcentage : « Élevé · 72 % » |
| `badge_status.html` | `status` | Session : `active` → vert « Active », `closed` → gris « Terminée », `invalid` → rouge « Invalide » |
| `badge_event.html` | `event` | Libellé et couleur de catégorie issus du presenter (§9) |
| `alert.html` | `level` (`success`/`error`/`warning`/`info`), `message` | `role="alert"` pour `error`/`warning`, `role="status"` pour le reste ; bouton de fermeture accessible |
| `messages.html` | — | Boucle sur `messages` Django ; correspondance niveau Django → niveau `alert` (`SUCCESS`→success, `ERROR`→error, `WARNING`→warning, `INFO`/`DEBUG`→info) |
| `empty_state.html` | `title`, `description`, `cta_label`, `cta_url` | Bloc centré avec icône SVG, jamais un tableau vide sans explication |
| `pagination.html` | `page_obj` | Précédent/Suivant + « Page X sur Y » ; **conserve tous les paramètres GET** (filtres) dans les liens |
| `form_field.html` | `field` | `<label for>` toujours visible, widget, aide `field.help_text`, erreurs ; `aria-invalid="true"` et `aria-describedby` pointant vers l'erreur si invalide |
| `copy_field.html` | `label`, `value` | Champ en lecture seule + bouton « Copier » (`data-copy-target`) ; retour visuel « Copié ✓ » annoncé via `aria-live="polite"` |
| `secret_field.html` | `label`, `reveal_url` | Valeur masquée `sk_live_••••••••`, bouton « Révéler » (§8.6.2). Aucune valeur secrète n'est présente dans le HTML initial |
| `confirm_dialog.html` | `id`, `title`, `message`, `confirm_label`, `form_action` | `<dialog>` natif avec `<form method="post">` + `{% csrf_token %}` ; bouton « Annuler » ; focus initial sur Annuler (action destructive = pas de confirmation accidentelle par Entrée) |

**Exemple de partial commenté (`components/badge_risk.html`) — niveau de commentaire attendu :**

```html
{% load dashboard_extras %}
{# Ce badge affiche le niveau de risque d'une session (BF-16).
   - `score` vaut None tant que la tâche Celery n'a pas fini : on l'affiche comme « Calcul en cours »
     plutôt que 0 %, sinon un score vide serait lu comme « aucun risque » (faux et trompeur).
   - Le libellé texte accompagne TOUJOURS la couleur (accessibilité : ne jamais compter sur la couleur seule).
   Exemple : score=0.72 → « Élevé · 72 % » en rouge ; score=None → « Calcul en cours » en gris. #}
{% if score is None %}
  <span class="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">Calcul en cours</span>
{% else %}
  {% risk_level score as level %}
  {% if level == "high" %}
    <span class="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800">Élevé · {% widthratio score 1 100 %} %</span>
  {% elif level == "medium" %}
    <span class="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">Moyen · {% widthratio score 1 100 %} %</span>
  {% else %}
    <span class="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">Faible · {% widthratio score 1 100 %} %</span>
  {% endif %}
{% endif %}
```
*(Les trois branches écrivent chaque classe en entier — règle du §2.2.)*

---

## 5. Code d'appui côté Python

### 5.1 `forms.py` — style des formulaires sans dépendance supplémentaire

```python
# Mixin qui applique les classes Tailwind à tous les widgets d'un formulaire.
# Pourquoi un mixin plutôt que django-widget-tweaks : cette librairie n'est pas dans le périmètre validé
# (05_AGENT_GUIDELINES §3) et le besoin se résout en 10 lignes.
class TailwindFormMixin:
    INPUT_CLASSES = (
        "block w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm "
        "focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            # Les cases à cocher/radios ont un style différent : on ne leur applique pas les classes de champ texte.
            if isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {self.INPUT_CLASSES}".strip()


class ProjectForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "site_url"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        # Exemple d'aide affichée sous le champ (utile car une mauvaise valeur désactive l'extension en silence) :
        help_texts = {"site_url": "Adresse où s'exécute votre plateforme d'examen, ex. https://examens.mon-universite.edu"}
```

### 5.2 `context_processors.py`

```python
def dashboard_context(request):
    """Injecte dans TOUS les templates le statut du développeur et les seuils de risque.

    getattr(..., None) est volontaire : pour un utilisateur sans profil Developer, l'accès au profil
    lève RelatedObjectDoesNotExist, qui hérite d'AttributeError — getattr renvoie donc None au lieu de planter.
    Exemple : un visiteur anonyme ou un futur type d'utilisateur non-développeur reçoit developer=None.
    """
    developer = getattr(getattr(request, "user", None), "developer_profile", None)
    return {
        "developer": developer,
        "developer_status": developer.status if developer else None,
        "risk_thresholds": settings.RISK_THRESHOLDS,   # {"medium": 0.3, "high": 0.6}
    }
```
Déclarer dans `settings.py` : `RISK_THRESHOLDS = {"medium": 0.3, "high": 0.6}` — **valeurs indicatives**, centralisées en un seul endroit, à ajuster après mesures réelles au Chapitre 3.

### 5.3 `templatetags/dashboard_extras.py` — filtres et tags

| Nom | Signature | Rôle | Exemple |
| :--- | :--- | :--- | :--- |
| `risk_level` (tag) | `score -> "low"\|"medium"\|"high"` | Compare au seuil `settings.RISK_THRESHOLDS` | `0.72 → "high"` |
| `duration` (filtre) | `seconds -> "1 h 12 min"` | Durée lisible d'une session | `4320 → "1 h 12 min"` |
| `offset` (filtre) | `event.timestamp, session.started_at -> "T+00:03:25"` | Décalage d'un événement depuis le début de la session | utile pour recouper avec le déroulé de l'examen |
| `tz_label` (tag) | — | Affiche le fuseau (« UTC ») à côté des horodatages | voir §17 |
| `mask_secret` (filtre) | `"sk_live_abc…1234" -> "sk_live_••••1234"` | N'est utilisé que pour afficher les 4 derniers caractères | |

---

## 6. Coquille du tableau de bord (`dashboard/base_dashboard.html`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ [☰ mobile]  Fil d'Ariane : Projets › Mon projet           [Prénom ▾]   │  ← topbar
├────────────┬─────────────────────────────────────────────────────────┤
│  ExamSDK    │  {% block page_header %} titre de page + boutons d'action │
│             │  {% include messages %}                                    │
│ ▣ Accueil    │  {% block content %}                                       │
│ ▣ Projets    │                                                           │
│ ▣ Doc API ↗  │                                                           │
│ ▣ Compte     │                                                           │
│             │                                                           │
│  v1.0       │                                                           │
└────────────┴─────────────────────────────────────────────────────────┘
```

| Élément | Contenu et règles |
| :--- | :--- |
| **Sidebar** (≥ `lg`) | Liens : **Accueil** (`dashboard:home`), **Projets** (`dashboard:project-list`), **Documentation API** (lien externe vers `/docs/redoc/`, `target="_blank" rel="noopener"`, icône ↗), **Compte** (`dashboard:account`). L'entrée courante porte `aria-current="page"` et un fond `bg-brand-50 text-brand-700` |
| **Mobile** (< `lg`) | Sidebar masquée ; le bouton ☰ (`aria-expanded`, `aria-controls="sidebar"`) l'affiche en tiroir. Fermeture : Échap, clic extérieur, ou sélection d'un lien |
| **Topbar** | Fil d'Ariane (`<nav aria-label="Fil d'Ariane">`), menu utilisateur : nom, email, lien « Compte », bouton « Se déconnecter » |
| **Déconnexion** | **Formulaire POST** vers `account_logout` avec `{% csrf_token %}` (allauth n'accepte pas un simple lien GET) |
| **Bannière de statut** | Au-dessus du contenu si `developer_status != "active"` (voir §7) |
| **Pied de sidebar** | Numéro de version de l'application (lecture seule) |

---

## 7. Statut du compte développeur → comportement de l'interface

`Developer.status` ∈ `pending` / `active` / `suspended` (UC-12, validé par l'administrateur dans Django Admin).

| Statut | Bannière | Ce que l'interface autorise | Ce que le backend fait déjà (`01_BACKEND.md`) |
| :--- | :--- | :--- | :--- |
| `pending` | Bleue : « Votre compte est en attente de validation par notre équipe. Vous pouvez préparer vos projets ; l'intégration ne sera opérationnelle qu'après validation. » | Lecture et création de projets autorisées | Sessions HMAC et inscription au `/public/registered-hosts/` refusées tant que non `active` |
| `active` | Aucune | Tout | — |
| `suspended` | Rouge : « Votre compte est suspendu. Contactez le support. » | **Lecture seule** : les boutons de création / modification / régénération / suppression sont **masqués ET refusés côté serveur** | Sessions HMAC refusées |

**Règle d'implémentation :** un mixin `ActiveDeveloperRequiredMixin` protège toutes les vues d'écriture (côté serveur, seule protection fiable) ; le masquage des boutons n'est qu'un confort visuel. Un accès POST direct d'un compte suspendu doit renvoyer 403.

*(Comportement proposé, non explicitement tranché dans les specs — voir §17.)*

---

## 8. Pages — contenu détaillé

**Table des routes internes du dashboard** (toutes sous `/dashboard/`, authentification par **session**, `LoginRequiredMixin` systématique) :

| Nom de route | Méthode | Chemin | Rôle | UC |
| :--- | :--- | :--- | :--- | :--- |
| `dashboard:home` | GET | `/dashboard/` | Accueil | — |
| `dashboard:project-list` | GET | `/dashboard/projects/` | Liste des projets | UC-2 |
| `dashboard:project-create` | GET, POST | `/dashboard/projects/new/` | Création | UC-2 |
| `dashboard:project-detail` | GET | `/dashboard/projects/<uuid>/?tab=` | Détail + onglets | UC-2/3/4/6 |
| `dashboard:project-edit` | GET, POST | `/dashboard/projects/<uuid>/edit/` | Modification | UC-2 |
| `dashboard:project-delete` | GET, POST | `/dashboard/projects/<uuid>/delete/` | Confirmation + suppression | UC-2 |
| `dashboard:project-reveal-secret` | POST | `/dashboard/projects/<uuid>/reveal-secret/` | Révéler la clé secrète (JSON) | UC-3 |
| `dashboard:project-regenerate-secret` | POST | `/dashboard/projects/<uuid>/regenerate-secret/` | Régénérer la clé secrète | UC-3 |
| `dashboard:session-detail` | GET | `/dashboard/sessions/<uuid>/` | Détail d'une session | UC-6 |
| `dashboard:account` | GET, POST | `/dashboard/account/` | Profil | UC-1 |
| `dashboard:account-delete` | GET, POST | `/dashboard/account/delete/` | Suppression du compte | UC-1 |

> **À ajouter dans `01_BACKEND.md` §6/§8** : `project-reveal-secret` (non listée dans la version actuelle alors que le bouton « Révéler » y est décrit).
> **Règle transversale :** une ressource appartenant à un autre développeur renvoie **404** (pas 403) — on ne révèle pas son existence. La vérification passe par le `TenantScopedManager` (`01_BACKEND.md` §4.4), jamais par un filtre écrit à la main dans la vue.

### 8.1 Racine `/`
Redirection : utilisateur authentifié → `/dashboard/` ; sinon → `/accounts/login/`. **Aucune page d'accueil marketing.**

### 8.2 Pages d'authentification (surcharges allauth)

Surcharger dans `templates/account/` et `templates/socialaccount/` pour appliquer la charte (carte centrée `max-w-md`, logo, composants du §4). **Vérifier la version installée d'allauth** : les versions récentes organisent leurs gabarits via `allauth/layouts/base.html` et `allauth/elements/*` (surcharger ces fichiers suffit à tout styler) ; les versions plus anciennes exigent de surcharger chaque page individuellement.

| Page | URL | Contenu |
| :--- | :--- | :--- |
| **Connexion** | `/accounts/login/` | Champs email + mot de passe ; case « Se souvenir de moi » ; lien « Mot de passe oublié ? » ; séparateur « ou » ; boutons **« Continuer avec Google »** et **« Continuer avec GitHub »** (icône SVG + libellé, pleine largeur) ; lien « Pas encore de compte ? S'inscrire » |
| **Inscription** | `/accounts/signup/` | Email, mot de passe, confirmation ; indications de robustesse du mot de passe ; mêmes boutons sociaux ; mention d'acceptation des conditions (lien) ; lien « Déjà inscrit ? Se connecter » |
| **Vérification d'email envoyée** | `/accounts/confirm-email/` | Message « Un lien de confirmation a été envoyé à *<email>*. Vous devez le confirmer avant de vous connecter » + bouton « Renvoyer l'email » |
| **Confirmation d'email** | `/accounts/confirm-email/<key>/` | Phrase « Confirmer que *<email>* est bien votre adresse » + bouton de confirmation (POST) ; état d'erreur si lien expiré |
| **Mot de passe oublié** | `/accounts/password/reset/` | Champ email, bouton d'envoi |
| **Email de réinitialisation envoyé** | `/accounts/password/reset/done/` | Message **identique que l'email existe ou non** (ne pas révéler l'existence d'un compte) |
| **Nouveau mot de passe** | `/accounts/password/reset/key/<…>/` | Deux champs + règles de robustesse ; état « lien invalide/expiré » avec lien pour en redemander un |
| **Réinitialisation terminée** | `…/done/` | Confirmation + bouton « Se connecter » |
| **Connexion sociale annulée / en erreur** | `/accounts/social/login/cancelled/`, `…/error/` | Message clair (« Connexion annulée » / « Échec de la connexion avec Google »), bouton « Retour à la connexion » |
| **Déconnexion** | `/accounts/logout/` | Page de confirmation (POST) si l'utilisateur y accède directement |

**Après inscription** : le signal `user_signed_up` crée le profil `Developer` (`01_BACKEND.md` §4). Redirection vers `/dashboard/`, où la bannière « en attente de validation » s'affiche (§7).

### 8.3 Accueil — `/dashboard/`

```
┌──────────────────────────────────────────────────────────────────┐
│ Bonjour, {{ prénom }}                                  [Nouveau projet] │
├───────────────┬───────────────┬──────────────────────────────────┤
│ Projets        │ Sessions       │ Événements critiques                │
│     3          │ actives  12    │ dernières 24 h   7                  │
├───────────────┴───────────────┴──────────────────────────────────┤
│ Alertes à examiner                                         [Voir tout ›] │
│  Session  | Projet     | Examen   | Étudiant | Score        | Date      │
│  a1b2…    | Univ-A     | MATH-101 | s-0042   | ● Élevé 81 % | 17/09 …   │
├──────────────────────────────────────────────────────────────────┤
│ Projets récents                                                          │
│  ┌ carte projet ┐ ┌ carte projet ┐ ┌ carte projet ┐                       │
└──────────────────────────────────────────────────────────────────┘
```

| Section | Données et règles |
| :--- | :--- |
| **Cartes de synthèse** (3) | (1) nombre de projets du développeur ; (2) sessions `status="active"` tous projets confondus ; (3) nombre d'événements **critiques** sur 24 h. « Critique » = les types de l'ensemble `CRITICAL_TYPES` du SDK (`02_SDK.md` §13.2) : `MULTIPLE_FACES`, `FORBIDDEN_OBJECT_DETECTED`, `AUDIO_KEYWORD_MATCH`, `EXTENSION_HEARTBEAT_LOST`, `AUTOMATION_DETECTED`, `SIMULATED_EVENT_DETECTED`, `REPEATED_HEAD_TURN`. Cette liste doit vivre à **un seul endroit** côté backend (constante partagée), pas être recopiée |
| **Alertes à examiner** | Les 10 sessions des 7 derniers jours au `risk_score` ≥ seuil « élevé », triées par score décroissant. Colonnes : session (lien), projet, examen, étudiant, badge de risque, date. Note sous le tableau : « Un score élevé est un **indicateur d'aide à la décision**, pas une preuve. La décision revient à l'établissement. » (cohérent avec le modèle hybride IA + validation humaine du Chapitre 1) |
| **Projets récents** | 3 à 5 cartes : nom, `site_url`, nb de sessions actives, lien « Ouvrir » |
| **État vide (premier lancement)** | Remplace tout le reste par une **liste de démarrage** cochable : ① Créer un projet ② Copier vos clés ③ Intégrer le SDK (lien vers l'onglet Intégration) ④ Faire installer l'extension aux testeurs ⑤ Lancer une session de test |
| **Rafraîchissement** | Lien « Actualiser » manuel. Pas de temps réel (hors périmètre) |

### 8.4 Liste des projets — `/dashboard/projects/`
- **En-tête** : titre « Projets » + bouton **Nouveau projet**.
- **Barre de filtre** : champ recherche par nom (GET `?q=`).
- **Tableau** : Nom (lien) · Site (`site_url`, tronqué avec `title` complet) · Sessions actives · Créé le · Actions (« Ouvrir »). Tri par date de création décroissante. Pagination 25/page.
- **État vide** : `empty_state` « Aucun projet pour l'instant » + bouton « Créer mon premier projet ».
- Sur mobile, le tableau devient une liste de cartes (colonnes secondaires masquées `hidden sm:table-cell`).

### 8.5 Formulaire de projet — `/dashboard/projects/new/` et `/<uuid>/edit/`

| Champ | Type | Règles de validation | Message d'erreur (exemple) |
| :--- | :--- | :--- | :--- |
| **Nom** | texte | obligatoire, ≤ 255 caractères | « Donnez un nom à votre projet. » |
| **Description** | zone de texte (3 lignes) | facultatif, ≤ 2 000 caractères | — |
| **Adresse du site** (`site_url`) | URL | obligatoire ; schéma `http` ou `https` ; un seul hôte ; hôte sans chemin utile (on en extrait le nom de domaine) ; **refuser `localhost` et les adresses IP littérales hors mode `DEBUG`** ; avertissement (non bloquant) si `http` | « Saisissez une adresse complète, ex. https://examens.mon-universite.edu » |

- **Aide sous `site_url` (obligatoire)** : « Cette adresse détermine où l'extension s'active chez vos étudiants. Une adresse incorrecte empêche la surveillance de démarrer. Les sous-domaines sont couverts automatiquement. »
- **Boutons** : « Enregistrer » (primaire), « Annuler » (retour à la liste ou au projet).
- **Après création** : le service `ProjectService.create_project` génère les clés (BF-05) ; redirection vers `project-detail?tab=keys` avec message « Projet créé. Vos clés API sont prêtes. »
- **Compte suspendu** : formulaire inaccessible (403, §7).

### 8.6 Détail d'un projet — `/dashboard/projects/<uuid>/?tab=`

**Coquille** : en-tête (nom du projet, `site_url`, boutons « Modifier » / « Supprimer »), puis barre d'onglets. **Onglets = liens GET `?tab=…`** (rendu serveur) : fonctionne sans JavaScript, l'URL est partageable, le bouton Retour fonctionne. Onglet actif : `aria-current="page"`, soulignement `border-brand-600`. Onglet inconnu ou absent → `overview`.

#### 8.6.1 Onglet « Vue d'ensemble » (`tab=overview`)
- Carte « Informations » : nom, description, `site_url`, date de création, statut du compte propriétaire.
- 3 chiffres : sessions totales, sessions actives, événements sur 30 jours.
- Lien « Voir les sessions » → onglet Sessions.

#### 8.6.2 Onglet « Clés API » (`tab=keys`) — UC-3
| Élément | Comportement |
| :--- | :--- |
| **Clé publique** | `copy_field` : valeur visible (`pk_live_…`), bouton « Copier ». Texte d'aide : « À placer dans le code de votre page d'examen (`publicKey`). Elle n'est pas confidentielle. » |
| **Clé secrète** | `secret_field` : affichée masquée `sk_live_••••••••`. Texte d'aide en rouge : « **Confidentielle.** À utiliser uniquement sur le serveur de votre plateforme pour signer les jetons de session. Ne jamais l'inclure dans du code exécuté dans un navigateur. » |
| **Bouton « Révéler »** | Ouvre un `<dialog>` de confirmation (« La clé va s'afficher à l'écran. Assurez-vous que personne ne regarde. ») → `fetch` **POST** vers `project-reveal-secret` (CSRF) → la valeur s'affiche dans un `<code>` avec bouton « Copier » → **remasquage automatique après 30 s** et effacement du nœud texte. La réponse du serveur porte `Cache-Control: no-store`, et chaque révélation écrit une entrée `AccessLog` (`action="reveal_secret"`) |
| **Bouton « Régénérer »** | `confirm_dialog` d'avertissement : « L'ancienne clé secrète sera **immédiatement invalidée** : les sessions signées avec elle cesseront d'être acceptées. Mettez à jour votre serveur juste après. » → POST `project-regenerate-secret` → retour sur l'onglet avec message de succès (la nouvelle clé est masquée ; utiliser « Révéler »). Écrit un `AccessLog` |
| **Compte suspendu** | Boutons Révéler/Régénérer masqués et refusés côté serveur |

#### 8.6.3 Onglet « Sessions » (`tab=sessions`) — UC-6, BF-19
- **Filtres (formulaire GET, valeurs conservées)** : examen (`exam_id`, texte), étudiant (`student_id`, texte), statut (liste : Toutes / Active / Terminée / Invalide), période (date de début, date de fin), bouton « Filtrer » et lien « Réinitialiser ».
- **Tableau** : Examen · Étudiant · Statut (`badge_status`) · Risque (`badge_risk`) · Début · Durée · lien « Détail ». Tri par début décroissant (en-têtes triables `?sort=`). Pagination 25/page.
- **Regroupement par examen** : le filtre `exam_id` répond au besoin du tableau de bord enseignant (« pour un examen précis, voir ce qui s'est passé »). Un compteur au-dessus du tableau indique « N sessions pour l'examen X ».
- **État vide** : « Aucune session ne correspond à ces critères » (si filtres) ou « Aucune session pour l'instant » + lien vers l'onglet Intégration.
- Chaque consultation écrit un `AccessLog` (`action="consultation"`, `resource_type="ExamSession"`), via le middleware commun — jamais à la main dans la vue.

#### 8.6.4 Onglet « Intégration » (`tab=integration`) — BF-25
Sections, de haut en bas :
1. **Prérequis** (liste cochée automatiquement quand c'est vérifiable) : `site_url` renseigné · compte actif · clés générées.
2. **Étape 1 — Installer le SDK** : extrait de chargement du SDK depuis l'URL du CDN du projet (variable de configuration `SDK_CDN_URL`, jamais codée en dur).
3. **Étape 2 — Générer le jeton de session côté serveur** : explication + exemples **Python** et **Node.js** (sélecteur de langage). Le jeton est signé avec la clé secrète selon le format de `01_BACKEND.md` §4.1 (chaîne canonique `project_id|exam_id|student_id|issued_at`, HMAC-SHA256). **Ces exemples doivent être testés** : un exemple faux fait échouer l'intégration de chaque développeur.
4. **Étape 3 — Initialiser le SDK dans la page d'examen** : extrait vanilla JS pré-rempli avec **la `public_key` réelle du projet** et `apiUrl` ; paramètres facultatifs commentés (`examKeywords`, `samplingIntervalMs`, `enabledDetectors`, `onBlock`) ; variante **React** (`ExamSurveillanceProvider`, `02_SDK.md` §16).
5. **Étape 4 — Informer vos étudiants** : texte prêt à copier expliquant l'extension à installer, l'accès caméra/micro, et ce qui est (et n'est pas) transmis (aucune image ni audio) ; lien vers la page de l'extension sur le Chrome Web Store.
6. **Liens** : « Documentation API (Swagger) » → `/docs/swagger/` · « Documentation de référence (Redoc) » → `/docs/redoc/`.
7. **Avertissement** : « Les mots-clés d'examen (`examKeywords`) sont transmis en clair au navigateur : ils sont visibles de l'étudiant qui inspecte la page » (limite assumée, `00_PROJECT_OVERVIEW.md` §9).

Chaque extrait de code est dans un `<pre><code>` avec un bouton « Copier » (`copy_field` variante bloc).

#### 8.6.5 Onglet « Paramètres » (`tab=settings`)
- Formulaire `ProjectForm` (mêmes champs et validations que §8.5), `action` vers `project-edit`.
- **Zone de danger** (encadré rouge) : « Supprimer ce projet » → page de confirmation §8.7.

### 8.7 Suppression d'un projet — `/dashboard/projects/<uuid>/delete/`
Page de confirmation (GET) puis suppression (POST) : rappel des conséquences (« Les clés cesseront de fonctionner ; les sessions et événements associés… » — formulation selon la décision §17), champ « Tapez le nom du projet pour confirmer », bouton rouge désactivé tant que la saisie ne correspond pas (vérifiée **aussi côté serveur**).

### 8.8 Détail d'une session — `/dashboard/sessions/<uuid>/` — UC-6

```
┌──────────────────────────────────────────────────────────────────┐
│ Session a1b2c3…    Projet Univ-A › MATH-101 › s-0042                    │
│ ● Terminée   Début 17/09 09:00 UTC   Durée 1 h 12 min                    │
│ Risque : ● Élevé · 81 %  ⓘ                                              │
├──────────────────────────────────────────────────────────────────┤
│ Résumé : 3 visages multiples · 1 mot-clé audio · 12 changements d'onglet │
├──────────────────────────────────────────────────────────────────┤
│ Filtres : [Type ▾] [Source ▾] [Critiques seulement ☐]                     │
│ ┃ T+00:03:25  ● Vision   Plusieurs visages   2 visages détectés   92 %   │
│ ┃ T+00:07:02  ● Navigateur  Perte de focus                                │
│ ┃ T+00:12:40  ● Audio    Mot-clé « mitochondrie » (2 segments)    75 %     │
│            ▸ Détails techniques                                           │
└──────────────────────────────────────────────────────────────────┘
```

| Section | Contenu et règles |
| :--- | :--- |
| **En-tête** | Identifiants `exam_id` / `student_id`, `badge_status`, début, fin, durée, `badge_risk`. L'icône ⓘ ouvre une info-bulle accessible (focus clavier) : « Score calculé automatiquement à partir du nombre, du type et de la confiance des événements. C'est un indicateur d'aide à la décision, pas une preuve de fraude. » |
| **Résumé** | Décompte des événements par type (les plus fréquents d'abord) |
| **Filtres** | Type (liste), source (SDK / Extension), « Critiques seulement » ; formulaire GET |
| **Chronologie** | Triée par horodatage **croissant**. Chaque ligne : décalage `T+hh:mm:ss` (filtre `offset`) + horodatage absolu au survol, `badge_event` (catégorie colorée), **phrase lisible** (presenter, §9), score de confiance en %. Les événements critiques ont une bordure gauche `border-l-4 border-red-500` |
| **Détails techniques** | `<details>` replié par ligne : `event_id`, `source`, `sdk_version`, `user_agent`, empreinte `integrity_hash` (tronquée), métadonnées brutes (JSON **échappé**) |
| **Pagination** | 50 événements/page, filtres conservés |
| **État vide** | « Aucun événement enregistré pour cette session » |
| **Traçabilité** | La consultation écrit un `AccessLog` (BNF-33) |
| **Pas de bouton de modification/suppression** | Les événements sont **immuables** (BNF-33) : l'interface n'expose aucune action d'édition |

### 8.9 Compte — `/dashboard/account/`
| Section | Contenu |
| :--- | :--- |
| **Profil** | Nom complet (modifiable, `Developer.full_name`) ; email (lecture seule ici) avec lien « Gérer mes adresses email » → `/accounts/email/` (page allauth surchargée) |
| **Comptes connectés** | Lien vers `/accounts/3rdparty/` (surcharge de `socialaccount/connections.html`) : liste Google / GitHub avec « Connecter » / « Déconnecter ». **Règle** : ne jamais permettre de déconnecter l'unique moyen de connexion (allauth le bloque ; le message d'erreur doit être traduit) |
| **Sécurité** | « Changer le mot de passe » (`/accounts/password/change/`) si un mot de passe existe ; sinon « Définir un mot de passe » (`/accounts/password/set/`) pour un compte 100 % social |
| **Zone de danger** | « Supprimer mon compte » → `/dashboard/account/delete/` : même schéma que §8.7 (saisie de l'email pour confirmer) |

### 8.10 Pages d'erreur
`403` (« Vous n'avez pas accès à cette page »), `404` (« Page introuvable »), `500` (« Une erreur est survenue »). Toutes : message clair, bouton « Retour à l'accueil », **aucun détail technique** (pas de trace, pas de chemin interne). `500.html` ne doit pas dépendre du contexte (il est rendu quand tout peut avoir échoué) : template autonome, sans `{% extends %}` ni context processor.

### 8.11 Administration — Django Admin natif
Aucun template custom. Seule personnalisation : `admin.site.site_header = "ExamSDK — Administration"`. Les modèles, actions (valider/suspendre un développeur) et le tableau de métriques sont décrits dans `01_BACKEND.md` §8.8.

---

## 9. Traduction des événements — `presenters.py`

**Principe :** le backend stocke des `EventType` techniques ; l'interface affiche des phrases lisibles par un enseignant. Un presenter central convertit `(type, metadata)` en `(libellé, catégorie, phrase, critique)`.

```python
# Présentation d'un événement pour le dashboard.
# Règles : (1) ne renvoie QUE du texte brut — jamais mark_safe : les métadonnées viennent d'un navigateur
# étudiant et ne sont donc pas dignes de confiance (risque XSS) ; l'auto-échappement de Django s'en charge.
# (2) Défensif : une clé absente ne doit jamais provoquer d'erreur — on retombe sur une phrase sans chiffres.
# Exemple : GAZE_AWAY_SUSTAINED + {"durationMs": 3400, "gaze": {"yawDeg": 32, "pitchDeg": 5}}
#           → « Regard détourné pendant 3,4 s (angle horizontal 32°, vertical 5°). »
def present_event(event) -> EventPresentation:
    spec = EVENT_PRESENTATION.get(event.type)
    if spec is None:
        # Type inconnu (ex. ajouté au SDK mais pas encore ici) : afficher le nom brut plutôt que planter.
        return EventPresentation(label=event.type, category="security", sentence="Événement non répertorié.", critical=False)
    return EventPresentation(label=spec["label"], category=spec["category"],
                             sentence=spec["sentence"](event.metadata or {}), critical=event.type in CRITICAL_TYPES)
```

### 9.1 Catégories et couleurs (classes écrites en entier)

| Catégorie | Libellé | Classes du badge |
| :--- | :--- | :--- |
| `browser` | Navigateur | `bg-blue-100 text-blue-800` |
| `vision` | Vision | `bg-purple-100 text-purple-800` |
| `audio` | Audio | `bg-teal-100 text-teal-800` |
| `extension` | Extension | `bg-indigo-100 text-indigo-800` |
| `security` | Sécurité | `bg-red-100 text-red-800` |

### 9.2 Table complète des 27 types (à tenir synchronisée avec `00_PROJECT_OVERVIEW.md` §7.1)

| `EventType` | Libellé | Cat. | Phrase affichée (champs de `metadata` utilisés) |
| :--- | :--- | :--- | :--- |
| `FOCUS_LOST` | Perte de focus | browser | « La fenêtre d'examen a perdu le focus. » |
| `TAB_SWITCH` | Changement d'onglet | browser | « Changement d'onglet ou fenêtre masquée. » |
| `COPY_PASTE_TEXT` | Copier-coller | browser | « Copier ou coller de texte détecté. » |
| `CLIPBOARD_IMAGE_PASTE` | Image collée | browser | « Une image a été collée depuis le presse-papiers. » |
| `PAGE_EXIT` | Sortie de page | browser | « Tentative de quitter la page d'examen. » |
| `DOM_TAMPERING` | Page modifiée | browser | « Modification suspecte de la page d'examen. » |
| `DEVTOOLS_OPEN` | Outils développeur | browser | « Outils de développement probablement ouverts (détection indicative). » |
| `AUTOMATION_DETECTED` | Automatisation | security | « Navigateur piloté par un script d'automatisation. » |
| `FULLSCREEN_EXIT` | Sortie plein écran | browser | « Sortie du mode plein écran. » |
| `PRINT_ATTEMPT` | Impression | browser | « Tentative d'impression. » |
| `SUSPICIOUS_KEY_COMBO` | Raccourci suspect | browser | « Raccourci clavier suspect{ : combo}. » |
| `IDLE_TIMEOUT` | Inactivité | browser | « Aucune activité pendant {idleMs/1000} s. » *(opt-in)* |
| `MULTI_MONITOR_DETECTED` | Plusieurs écrans | browser | « Plusieurs écrans détectés. » *(opt-in)* |
| `NO_FACE_DETECTED` | Aucun visage | vision | « Aucun visage détecté dans l'image. » |
| `MULTIPLE_FACES` | Plusieurs visages | vision | « {count} visages détectés. » |
| `FORBIDDEN_OBJECT_DETECTED` | Objet interdit | vision | « Objet interdit détecté : {label} (confiance {confidence}). » |
| `VIRTUAL_DEVICE_DETECTED` | Périphérique virtuel | vision | « Caméra ou micro virtuel détecté (indicatif, liste de noms connus). » |
| `GAZE_AWAY_SUSTAINED` | Regard détourné | vision | « Regard détourné pendant {durationMs/1000} s (angle horizontal {gaze.yawDeg}°, vertical {gaze.pitchDeg}°). » |
| `REPEATED_HEAD_TURN` | Tête tournée | vision | « Tête tournée {occurrences} fois en {windowMs/1000} s. » |
| `HANDS_VISIBLE_SUSTAINED` | Mains visibles | vision | « Mains visibles dans le champ pendant {durationMs/1000} s. » |
| `AUDIO_KEYWORD_MATCH` | Mot-clé audio | audio | « Mot-clé d'examen entendu : « {keyword} » (confirmé sur {confirmedOccurrences} segments). » |
| `MULTIPLE_VOICES` | Plusieurs voix | audio | « {voiceCount} voix distinctes détectées. » |
| `TAB_CHANGE_EXT` | Onglet (extension) | extension | « Changement d'onglet détecté par l'extension. » |
| `NAVIGATION_EXT` | Navigation (extension) | extension | « Navigation vers {hostname}. » — **afficher uniquement le nom de domaine, jamais l'URL complète** (minimisation : le chemin peut révéler des informations personnelles). À signaler à l'extension/backend : tronquer à la source |
| `SUSPICIOUS_ENVIRONMENT` | Environnement atypique | extension | « Environnement atypique (résolution anormale : {abnormalResolution}, écrans : {displayCount}). » |
| `EXTENSION_HEARTBEAT_LOST` | Extension injoignable | security | « L'extension ne répond plus : la poursuite de l'examen a été bloquée. » |
| `SIMULATED_EVENT_DETECTED` | Événement simulé | security | « Tentative d'injection d'événements simulés. » |

**Formatage des nombres** : durées avec une décimale et virgule française (« 3,4 s »), confiance en pourcentage entier (« 87 % »). Les métadonnées d'un type absent ou malformé n'empêchent jamais l'affichage (phrase de repli sans chiffres).

---

## 10. JavaScript — `static/js/dashboard.js`

Un seul fichier, vanilla, chargé en `defer`. **Chaque fonction est commentée (pourquoi, exemple).** Initialisation unique sur `DOMContentLoaded` qui appelle les fonctions ci-dessous ; chacune est inerte si ses éléments sont absents de la page.

| Fonction | Rôle | Points d'attention |
| :--- | :--- | :--- |
| `initSidebarToggle()` | Ouvre/ferme le tiroir mobile | Met à jour `aria-expanded` ; ferme sur Échap, clic extérieur et sélection d'un lien |
| `initCopyButtons()` | Boutons `[data-copy-target]` : copie via `navigator.clipboard.writeText` | Repli `document.execCommand('copy')` si l'API est indisponible (page non sécurisée) ; annonce « Copié » dans une zone `aria-live="polite"`, retour au libellé initial après 2 s |
| `initDialogs()` | Ouvre un `<dialog>` via `[data-dialog-open="id"]` (`showModal()`), ferme via `[data-dialog-close]` | Le focus initial est sur « Annuler » pour les actions destructives |
| `initSecretReveal()` | Gère « Révéler » : confirmation → `fetch` POST (en-tête `X-CSRFToken` lu dans `<body data-csrf>`) → affichage → remasquage après 30 s | La valeur n'est **jamais** stockée dans un attribut, le `localStorage` ni l'URL ; en cas d'erreur réseau, message explicite et aucun affichage partiel |
| `initConfirmByTyping()` | Active le bouton destructeur seulement quand le champ saisi égale la valeur attendue | Simple confort : la vérification réelle est **côté serveur** |
| `initFlashMessages()` | Bouton de fermeture des alertes | Les messages d'erreur ne disparaissent jamais automatiquement |

**Interdits :** pas de `innerHTML` avec des données serveur (utiliser `textContent`), pas de `eval`, pas de bibliothèque ajoutée.

---

## 11. Sécurité côté interface

- **CSRF** : `{% csrf_token %}` dans chaque `<form method="post">` ; les `fetch` POST envoient `X-CSRFToken`. Ne jamais désactiver la protection.
- **Échappement** : l'auto-échappement Django reste actif partout. **Interdit : `|safe` et `mark_safe` sur toute donnée venant d'un navigateur** (métadonnées d'événements, `student_id`, `exam_id`, `user_agent`).
- **Isolation multi-tenant** : aucune vue ne charge un objet par `pk` seul ; toujours via le gestionnaire scopé (404 si autre tenant). Les liens générés dans les templates n'exposent jamais d'identifiants d'autres développeurs.
- **Clé secrète** : absente du HTML initial, des journaux, des URL et des messages d'erreur ; transite uniquement dans la réponse `no-store` de `project-reveal-secret`.
- **Liens externes** : `rel="noopener noreferrer"` systématique avec `target="_blank"`.
- **Champs sensibles** : attributs `autocomplete` corrects (`current-password`, `new-password`, `email`).
- **Pas de contenu tiers** hors CDN Tailwind : aucune police, analytics ou script externe.

---

## 12. Accessibilité (WCAG AA) — liste de contrôle

- [ ] Lien d'évitement « Aller au contenu principal » présent (§2.1)
- [ ] Un seul `<h1>` par page ; hiérarchie de titres continue
- [ ] Tous les champs ont un `<label>` associé ; erreurs liées par `aria-describedby`, `aria-invalid` posé
- [ ] Focus clavier visible sur tout élément interactif (`focus-visible:ring-2`)
- [ ] Contraste ≥ 4,5:1 (texte), ≥ 3:1 (composants graphiques) ; couleur jamais seule porteuse d'information
- [ ] Onglets, dialogues, menu mobile utilisables au clavier ; Échap ferme dialogues et tiroir
- [ ] Messages dynamiques annoncés (`role="status"` / `role="alert"`, `aria-live`)
- [ ] Tableaux avec `<th scope="col">` et `<caption class="sr-only">`
- [ ] Texte alternatif ou `aria-hidden="true"` sur les icônes SVG décoratives
- [ ] Zoom 200 % sans perte de contenu ; cibles tactiles ≥ 44×44 px sur mobile

---

## 13. Responsive et performance

- **Mobile d'abord** : points de rupture Tailwind `sm` (640), `md` (768), `lg` (1024). La sidebar n'est fixe qu'à partir de `lg`.
- Tableaux : colonnes secondaires masquées sous `sm` ; défilement horizontal `overflow-x-auto` en dernier recours.
- Pagination côté serveur partout (25 projets / 25 sessions / 50 événements par page) : jamais de liste non bornée.
- Requêtes : `select_related`/`prefetch_related` dans les vues ; objectif indicatif ≤ 10 requêtes SQL par page (à vérifier en test).
- Aucune image lourde ; icônes en SVG inline.

---

## 14. Tests du frontend (complète `04_TESTS.md` §1 et §4)

| Test | Type | Vérifie |
| :--- | :--- | :--- |
| Rendu 200 de chaque page pour le propriétaire | Django `TestCase` | Contexte attendu, templates utilisés |
| Ressource d'un autre tenant → **404** (pages projet, session, reveal, regenerate, delete) | Django `TestCase` | Isolation sur les vues templates (`04_TESTS.md` §1.3) |
| Compte `suspended` : POST de création/modification/régénération → 403 | Django `TestCase` | Protection serveur (§7) |
| Réponse de `project-reveal-secret` : `Cache-Control: no-store` + `AccessLog` écrit | Django `TestCase` | §8.6.2 |
| Le HTML initial de l'onglet Clés **ne contient pas** la clé secrète | Django `TestCase` | §11 |
| Presenter : chaque `EventType` du SDK a une entrée ; métadonnées absentes → pas d'exception | pytest | §9 (test de parité avec l'enum) |
| Presenter : une métadonnée contenant `<script>` est échappée dans le HTML rendu | Django `TestCase` | Anti-XSS |
| Pagination conserve les filtres GET | Django `TestCase` | §4 |
| Parcours inscription → vérification email → dashboard ; connexion sociale | Playwright | `04_TESTS.md` §4.2 |
| Accessibilité automatique de chaque page (axe-core) | Playwright | §12 |
| Menu mobile, révélation puis remasquage de la clé à 30 s (horloge simulée) | Playwright | §10 |

---

## 15. Livrables frontend

- [ ] `templates/base.html`, `403/404/500.html`, `components/*.html` (§4)
- [ ] `templates/account/*` et `templates/socialaccount/*` (surcharges allauth, §8.2)
- [ ] `apps/dashboard/templates/dashboard/*` (toutes les pages et onglets, §8)
- [ ] `apps/dashboard/presenters.py`, `forms.py`, `context_processors.py`, `templatetags/dashboard_extras.py`
- [ ] `static/css/custom.css`, `static/js/dashboard.js`
- [ ] Section « Frontend » dans `backend/SETUP.md` : accès Internet requis pour le CDN Tailwind, `SDK_CDN_URL`, `RISK_THRESHOLDS`, `collectstatic`, **rappel de migrer le CDN avant toute mise en production** (§2.4)
- [ ] Tests du §14

## 16. Hors périmètre (rappel)
Landing marketing · temps réel/WebSocket · export CSV/PDF des événements · graphiques · mode sombre · application mobile · tableau de bord admin custom · notifications push/email de produit (hors emails d'authentification allauth).

---

## 17. Points à valider avant implémentation (ne pas trancher seul — règle n°1)

| # | Point | Proposition par défaut | Pourquoi c'est important |
| :--- | :--- | :--- | :--- |
| 1 | **Suppression de projet/compte vs immuabilité des événements.** `01_BACKEND.md` prévoit `REVOKE DELETE` sur `events` (BNF-33) **et** `on_delete=CASCADE` depuis `Project`/`Developer`. Les deux sont incompatibles : supprimer un projet tenterait de supprimer des événements | « Suppression » = **archivage** (`is_archived`, clés désactivées, données conservées selon une durée de rétention) ; purge définitive par une tâche de maintenance privilégiée distincte, avec trace d'audit (cohérent avec BNF-34) | Sans arbitrage, la suppression plantera en production ou l'immuabilité sera contournée |
| 2 | Comportement des comptes `pending` / `suspended` (§7) | Tel que décrit au §7 | Le statut n'est qu'esquissé dans les specs |
| 3 | Fuseau d'affichage des horodatages | Tout en **UTC**, libellé « UTC » affiché partout (valeur probante) ; fuseau par profil ultérieurement | Les heures d'examen sont lues par des enseignants dans des fuseaux variés |
| 4 | Langue de l'interface | Français, textes dans `{% translate %}` pour permettre l'anglais plus tard | Coût marginal maintenant, refonte coûteuse après |
| 5 | Endpoint `project-reveal-secret` | À ajouter à `01_BACKEND.md` ; ou, alternative plus stricte, n'afficher la clé qu'à la création/régénération | Décrit dans le §8.5 de `01_BACKEND.md` sans route associée |
| 6 | `NAVIGATION_EXT` : l'extension envoie l'URL complète (`03_EXTENSION.md` §9.1) | Tronquer au nom de domaine **à la source** (extension) | Minimisation des données ; le dashboard ne doit pas être le seul rempart |
| 7 | Seuils de risque (0,3 / 0,6) | Indicatifs, centralisés dans `settings.RISK_THRESHOLDS` | À calibrer sur des données réelles au Chapitre 3 |
| 8 | Tailwind CDN | Accepté pour le prototype uniquement (§2.3) | Migration obligatoire avant production |
