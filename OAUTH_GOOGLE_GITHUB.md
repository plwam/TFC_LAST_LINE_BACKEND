# OAuth Google & GitHub — URL à déclarer et où configurer

Ce document liste **exactement** les URL à enregistrer dans la Google Cloud Console et dans
les « OAuth Apps » GitHub pour que la connexion sociale d'EvaSee fonctionne, et rappelle où la
configuration vit dans le projet.

Tout est déjà branché côté backend : il ne reste qu'à créer les applications OAuth chez les
fournisseurs et remplir le `.env`.

---

## 1. Où la configuration vit dans le projet

| Élément | Fichier | Détail |
| --- | --- | --- |
| Providers activés | `config/settings/base.py` | lignes 55-56 (`allauth.socialaccount.providers.google` / `.github`) |
| URL d'allauth montées | `config/urls.py` | ligne 35 : `path("accounts/", include("allauth.urls"))` |
| Identifiants lus depuis l'environnement | `config/settings/base.py` | `SOCIALACCOUNT_PROVIDERS`, lignes 217-233 |
| Variables d'environnement | `.env` (copie de `.env.example`) | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET` |
| Boutons sur la page de connexion | `templates/allauth/...` | un provider **sans** identifiants n'apparaît pas (voir §6) |

Les identifiants ne sont **jamais** en dur dans le code (règle `01_BACKEND.md` §14). Un provider
laissé vide désactive simplement son bouton : le reste du site (email / mot de passe) continue
de fonctionner.

---

## 2. Les URL de redirection (redirect / callback URI)

C'est la **seule** URL dont chaque fournisseur a besoin. Le chemin est **imposé par allauth** et
ne doit jamais être modifié.

| Fournisseur | Chemin de callback (imposé par allauth) | Nom d'URL Django |
| --- | --- | --- |
| Google | `/accounts/google/login/callback/` | `google_callback` |
| GitHub | `/accounts/github/login/callback/` | `github_callback` |

On y préfixe l'origine (schéma + domaine + port). L'origine **doit correspondre au caractère
près** (schéma, hôte, port, chemin et **slash final**) à celle utilisée par le navigateur, sinon
le fournisseur renvoie une erreur `redirect_uri_mismatch`.

### Développement (runserver local)

```
http://localhost:8000/accounts/google/login/callback/
http://localhost:8000/accounts/github/login/callback/
http://127.0.0.1:8000/accounts/google/login/callback/
http://127.0.0.1:8000/accounts/github/login/callback/
```

> Déclarer **les deux** formes (`localhost` **et** `127.0.0.1`) : selon la façon dont on ouvre la
> page, l'origine change.

### Production

Remplacer `app.evasee.example` par le vrai domaine public (HTTPS obligatoire pour Google) :

```
https://app.evasee.example/accounts/google/login/callback/
https://app.evasee.example/accounts/github/login/callback/
```

> Ajouter aussi une ligne `http://...` ou `https://...` **par domaine supplémentaire** si le
> site répond sur plusieurs noms d'hôte (ex. `www.` + domaine nu, ou domaine de préproduction).

---

## 3. Google — Google Cloud Console

1. Aller sur <https://console.cloud.google.com/> et sélectionner (ou créer) un **projet**.
2. **Écran de consentement OAuth** (*APIs & Services → OAuth consent screen*) :
   - Type : **External** (sauf Workspace interne → **Internal**).
   - Renseigner nom de l'app « EvaSee », e-mail d'assistance, domaine autorisé si demandé.
   - **Scopes** : ajouter `.../auth/userinfo.email` et `.../auth/userinfo.profile`
     (ce sont les scopes `profile` + `email` déclarés dans `SOCIALACCOUNT_PROVIDERS`).
   - Tant que l'app est en mode **Testing**, ajouter les comptes testeurs dans
     *Test users* (sinon seuls ces comptes peuvent se connecter).
3. **Identifiants** (*APIs & Services → Credentials*) :
   - *Create credentials* → **OAuth client ID**.
   - Type d'application : **Web application**.
   - **Authorized JavaScript origins** : ajouter l'origine seule, sans chemin
     (`http://localhost:8000` en dev, `https://app.evasee.example` en prod).
   - **Authorized redirect URIs** : coller les URL du §2 (Google).
   - *Créer* → copier le **Client ID** et le **Client secret**.
4. Reporter ces valeurs dans `.env` :

   ```dotenv
   GOOGLE_OAUTH_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=xxxxxxxx
   ```

---

## 4. GitHub — OAuth App

1. Se connecter à GitHub → **Settings → Developer settings → OAuth Apps** (ou au niveau de
   l'organisation : *Organization settings → Developer settings → OAuth Apps*).
2. **New OAuth App** :
   - **Application name** : « EvaSee ».
   - **Homepage URL** : `http://localhost:8000` (dev) ou `https://app.evasee.example` (prod).
   - **Authorization callback URL** : **une seule** URL autorisée par app —
     `http://localhost:8000/accounts/github/login/callback/` (dev) ou
     `https://app.evasee.example/accounts/github/login/callback/` (prod).
     > GitHub ne permet qu'une seule callback par app : créer des apps distinctes par
     > environnement (dev / prod).
3. *Register application* → **Generate a new client secret** → copier **Client ID** et
   **Client secret**.
4. Reporter ces valeurs dans `.env` :

   ```dotenv
   GITHUB_OAUTH_CLIENT_ID=Iv1.xxxxxxxxxxxx
   GITHUB_OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxx
   ```

> Le scope GitHub utilisé est `user:email` (déjà défini dans `SOCIALACCOUNT_PROVIDERS`) : il
> permet de récupérer l'e-mail vérifié du compte, nécessaire car EvaSee identifie les comptes
> par l'e-mail (`ACCOUNT_LOGIN_METHODS = {"email"}`).

---

## 5. Rediriger l'utilisateur vers le bouton (rappel)

Les URL de **départ** (boutons) sont fournies par allauth, il n'y a rien à déclarer côté
fournisseur pour elles :

```
/accounts/google/login/     (nom : google_login)
/accounts/github/login/     (nom : github_login)
```

Après un login social réussi, allauth redirige vers `LOGIN_REDIRECT_URL = "dashboard:home"`
(`config/settings/base.py:195`), et crée automatiquement le profil `Developer`
(`SOCIALACCOUNT_AUTO_SIGNUP = True`, signal `apps/developers/signals.py`).

---

## 6. Checklist de vérification

1. `.env` rempli avec les 4 valeurs (les 2 providers ou un seul, au choix).
2. **Redémarrer** `runserver` après modification du `.env` (les settings sont lus au démarrage).
3. Le domaine du **`Site`** Django correspond à l'hôte réel. allauth s'en sert pour construire
   des liens absolus (notamment les e-mails de vérification) :

   ```powershell
   & ".venv\Scripts\python.exe" manage.py shell -c "from django.contrib.sites.models import Site; print(Site.objects.get(pk=1).domain)"
   ```

   Par défaut il vaut `example.com` — le corriger dans l'admin Django (`/admin/`, modèle Sites)
   ou :

   ```powershell
   & ".venv\Scripts\python.exe" manage.py shell -c "from django.contrib.sites.models import Site; s=Site.objects.get(pk=1); s.domain='localhost:8000'; s.name='EvaSee'; s.save()"
   ```

4. Vérifier que l'URL de callback déclarée chez le fournisseur est **identique** à celle-ci :

   ```powershell
   & ".venv\Scripts\python.exe" manage.py shell -c "from django.urls import reverse; print(reverse('google_callback')); print(reverse('github_callback'))"
   ```

5. En production, `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` (`.env`) doivent contenir le
   domaine utilisé, et le site doit être servi en **HTTPS** (Google l'exige).

---

## 7. Dépannage rapide

| Symptôme | Cause probable |
| --- | --- |
| `Error 400: redirect_uri_mismatch` | L'URL déclarée ne correspond pas exactement (schéma, port, `localhost` vs `127.0.0.1`, slash final). Revoir §2. |
| Aucun bouton Google/GitHub sur `/accounts/login/` | `GOOGLE_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_ID` vide, ou `runserver` non redémarré après `.env`. |
| `Origin mismatch` / blocage Google | Origine absente de *Authorized JavaScript origins* (§3). |
| GitHub : callback refusée | GitHub n'accepte qu'une callback par app → créer une app par environnement (§4). |
| Connexion Google refusée (accès bloqué) | App en *Testing* et compte non listé dans *Test users*, ou écran de consentement non finalisé. |
| E-mail de vérification pointe vers `example.com` | Domaine du `Site` (SITE_ID=1) à corriger (§6.3). |
