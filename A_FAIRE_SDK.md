# À FAIRE — Intégration du SDK (à reprendre plus tard)

> **Statut : EN ATTENTE.** À reprendre quand on implémentera le **module SDK** (spec
> `02_SDK.md`, non encore accessible dans ce périmètre). Le dashboard expose déjà l'onglet
> « Intégration » (4 étapes) et les endpoints machine, mais le client SDK lui-même n'existe
> pas encore. Ce fichier sert de mémoire de reprise.

## Décisions à figer (bloquant avant de coder le SDK)

- [ ] **Chaîne canonique HMAC** : l'onglet Intégration signe
      `project_id|exam_id|student_id|issued_at` (`_integration.html`), alors que
      `05_AGENT_GUIDELINES.md` mentionne `project_id|session_id|issued_at`. Choisir LA source
      de vérité, puis aligner : snippet du dashboard + `apps/machine_api/` + tests + spec.
- [ ] **`exam_id`** : clé stable fournie par la plateforme cliente (slug ?) vs `session_id`
      interne. Nommer et documenter la relation.
- [ ] **`SDK_CDN_URL`** : remplacer la valeur par défaut
      (`https://cdn.examsdk.local/sdk/v1/examsdk.js`, `config/settings/base.py`) par l'URL CDN
      réelle (env / prod).

## Backend à compléter

- [ ] Vérifier/compléter les endpoints consommés par le SDK dans `apps/machine_api/`
      (auth HMAC, ingestion d'événements, ouverture/fermeture de session).
- [ ] **CORS** : autoriser l'`apiUrl` depuis les domaines des `project.site_url`
      (django-cors-headers ?) — nécessaire car le SDK s'exécute sur le site client.
- [ ] **Whitelist des hôtes** (`registered-hosts`) : confirmer qu'elle dérive bien de
      `project.site_url` et vérifier le format exact attendu par l'extension.
- [ ] **Rate limit** ingestion (600/min) : valider la valeur et son implémentation.

## Templates / dashboard

- [ ] Aligner les 4 étapes de
      `apps/dashboard/templates/dashboard/project_tabs/_integration.html` sur la spec
      `02_SDK.md` §5 et §17 (signature exacte de `ExamSDK.init`, options : `examKeywords`,
      `samplingIntervalMs`, `enabledDetectors`, `onBlock`).
- [ ] Conserver l'avertissement « `examKeywords` transmis en clair ».
- [ ] Pointer les liens vers la page de doc maison `/docs/` (en plus de Swagger/Redoc).

## Tests

- [ ] Ajouter des tests couvrant l'onglet d'intégration (clé publique injectée, `sdk_cdn_url`,
      extraits non vides, schéma d'URL cohérent avec la décision ci-dessus).

## Références (fichiers concernés)

- `apps/dashboard/templates/dashboard/project_tabs/_integration.html`
- `apps/dashboard/views.py` (contexte `sdk_cdn_url`, `project.public_key`)
- `apps/machine_api/` (authentification HMAC, schéma OpenAPI)
- `apps/public/views.py` (`registered-hosts`, health)
- `config/settings/base.py` (`SDK_CDN_URL`)
