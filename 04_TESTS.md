# 04 — GUIDE DES TESTS AUTOMATIQUES (backend + SDK)

> Ce document explique COMMENT les tests du projet sont écrits, QUOI ils vérifient,
> QUELS fichiers concerner et COMMENT les lancer (par module et par type).

---

## 1. Vue d'ensemble : deux suites indépendantes

| Suite | Outil | Emplacement | État au 14/11/2026 |
|---|---|---|---|
| **Backend** (Django) | pytest + pytest-django | `backend/tests/` | 147 passed |
| **SDK** (TypeScript) | Vitest | `SDK/tests/` | 130 passed |
| **Charge** (script) | Python pur (pas pytest) | `backend/tests/load_simulation.py` | script, backend requis |

Les deux suites testent **le même contrat** de deux côtés : les chaînes canoniques HMAC
(`project_id|exam_id|student_id|issued_at`, etc.) sont reconstruites par les tests pytest
ET par les tests Vitest. Si un côté change sa canonique sans l'autre, les tests échouent
des deux côtés — c'est voulu (`00_PROJECT_OVERVIEW.md` §7).

---

## 2. Typologie : quel type de test, où, et pourquoi

### 2.1 Backend — `backend/tests/`

| Type | Fichiers | Ce qu'ils vérifient |
|---|---|---|
| **Unitaires** (pur, sans HTTP) | `test_presenters.py`, `test_forms.py`, `test_events.py` (partie sérialisation) | Fonctions isolées : formatage, validation de formulaire, calculs. Rapides, une fabrique chacun. |
| **Intégration API** (requête HTTP complète) | `test_projects_api.py`, `test_accounts_login.py`, `test_contact.py`, `test_public.py`, `test_admin.py`, `test_templates.py` | End-to-end dans le processus Django : requête DRF → vue → base → réponse. Vérifient codes HTTP, contenu JSON, audit. |
| **Sécurité — HMAC** | `test_machine_api.py` | LA surface la plus exposée : signature, temps constant, fraîcheur `issued_at`, rejeu, idempotence, clés de chambre. Zéro Trust : TOUTE divergence → 401. |
| **Sécurité — multi-tenant** | `test_tenant_isolation.py` | Un développeur ne voit JAMAIS les objets d'un autre (404, jamais 403 : on ne révèle pas l'existence d'une ressource). |
| **Métier** | `test_risk_score.py`, `test_suspension.py`, `test_project_status.py`, `test_sdk_logs.py` | Calculs de score, machine à états des projets/sessions, ingestion du journal SDK. |
| **Garde-fou configuration** | `test_jwt_signing_key.py` | La clé de signature JWT fait ≥ 32 octets (RFC 7518 §3.2). Un test qui ÉCHOUE si un `.env` mal recopié remet une clé courte — fail fast, pas un warning ignoré. |
| **Performance / charge** | `tests/load_simulation.py` (script) | Simule N étudiants simultanés : ouverture, lots d'événements (7 s), heartbeats (45 s), clôture — signature par signature. Produit les chiffres du tableau 3:X7 du mémoire. **Nécéssite le backend allumé.** |

### 2.2 SDK — `SDK/tests/`

| Type | Fichiers | Ce qu'ils vérifient |
|---|---|---|
| **Unitaires — logique pure** | `ai/visionMath.test.ts`, `ai/textMatch.test.ts`, `ui/facemeshTopology.test.ts`, `logger/Logger.test.ts`, `i18n/i18n.test.ts` | Math des angles du regard, filtrage de mots-clés, topologie du maillage facial, niveau de log, traductions. Aucun réseau. |
| **Unitaires — orchestration** | `core/EventBus.test.ts`, `ai/BehaviorAggregator.test.ts`, `events/EventNormalizer.test.ts`, `events/EventClassifier.test.ts`, `events/EventQueue.test.ts`, `events/EventPipeline.test.ts` | Bus d'événements, agrégation comportementale (QUAND un événement existe), normalisation, classification (COMMENT VITE il part), file, pipeline. |
| **Intégration — transport** | `transport/HttpTransport.test.ts` | Cycle de session machine avec `fetch` MOQUÉ : URLs appelées, corps JSON, signatures HMAC exactes, retries, regroupement par session, clé de chambre. |
| **Intégration — diagnostics** | `diagnostics/Diagnostics.test.ts` | Heartbeats, journal, envoi du log. |
| **Intégration — extension** | `extension-bridge/ExtensionBridge*.test.ts` | Handshake SDK↔extension (états DISCONNECTED → CONNECTED, timeout → BLOCKED). |
| **Config / contrat** | `config/SdkConfig.test.ts`, `index.test.ts` | Validation de configuration (champs requis selon le mode), surface publique du SDK. |
| **Comportement métier** | `voice/VoiceWarnings.test.ts`, `dom-detectors/detectors.test.ts` | Seuils d'avertissement vocal, détecteurs DOM (dont DevTools). |

### 2.3 Ce qui N'EST PAS testé automatiquement (et pourquoi)

- **Vraie IA (TensorFlow.js)** : les modèles COCO-SSD/MediaPipe ne tournent pas en test —
  on teste la MATH autour (visionMath), pas l'inférence.
- **Vrais appels réseau** : tous les `fetch` sont moqués (`vi.fn()`). Un test qui dépend
  d'un serveur allumé serait instable (flaky).
- **Le navigateur réel** : la page de test (`SDK/test-page/`) sert de test manuel visuel,
  pas automatisé.

---

## 3. Comment on écrit un test (méthode, pas à pas)

### 3.1 La recette (celle que suivent tous les tests du projet)

1. **Lire le contrat d'abord** — jamais de test écrit à l'aveugle :
   - côté backend : le docstring du module testé (`01_BACKEND.md §…`, docstrings des vues) ;
   - côté SDK : le contrat backend (`backend/apps/machine_api/authentication.py`) ET les
     canoniques documentées — les tests reconstruisent la chaîne canonique **à la main**.
2. **Reconstruire le scénario réel** : les tests passent par les mêmes services que
   l'application (`ProjectService.create_project`, pas un `Project.objects.create()` nu)
   pour exercer le vrai chemin (génération de clés, chiffrement, audit).
3. **Structure AAA** dans chaque test :
   - **Arrange** — fixtures + chaîne canonique signée ;
   - **Act** — un seul appel `APIClient().post(...)` ou `transport.sendNow(...)`;
   - **Assert** — statut HTTP précis (202, 401, 404), contenu de réponse, état en base.
4. **Tester le REFUS autant que l'acceptation** : pour chaque cas nominal, au moins un cas
   d'attaque (signature fausse, horodatage périmé, clé d'un autre projet, session d'un autre
   tenant). C'est le cœur des `test_machine_api.py` et `test_tenant_isolation.py`.
5. **Docstring = le POURQUOI** : chaque test (comme chaque fonction du code) explique
   pourquoi il existe, pas ce qu'il fait ligne à ligne.

### 3.2 Exemple concret (clé de chambre, ajout du 14/11/2026)

```python
def test_events_signed_with_room_key(project, session, machine_headers, now_epoch):
    """Signature par la clé de chambre uniquement (sans clé maîtresse) → lot accepté."""
    room_key = derive_session_key(str(project.secret_key), str(session.id))
    message = f"{project.id}|{session.id}|{now_epoch}"
    response = APIClient().post(
        EVENTS_URL,
        {"session_id": str(session.id), "issued_at": now_epoch,
         "events": [{"event_id": "rk2", "type": Event.Type.FOCUS_LOST,
                     "occurred_at": timezone.now().isoformat()}]},
        format="json",
        # Le SDK signe le MESSAGE avec la clé de chambre (pas la clé elle-même en en-tête).
        **machine_headers(message, signature=sign_message(room_key, message)),
    )
    assert response.status_code == 202
    assert response.data == {"accepted": 1, "duplicates": 0}
```

Points clés :
- `machine_headers` (fixture) signe par défaut avec la clé maîtresse ; on la SURCHARGE
  avec `signature=` pour simuler le SDK post-initiation ;
- le message signé est reconstruit à la main — si la canonique change, le test pète ;
- l'assertion vérifie le statut ET le compteur (`accepted`) : tester la réponse entière.

### 3.3 Exemple côté SDK (moquage de fetch)

```typescript
const fetchImpl = vi.fn()
  .mockResolvedValueOnce({                    // 1er appel : ouverture de session
    ok: true, status: 201,
    json: () => Promise.resolve({ session_id: 'sess-1', session_key: roomKey }),
  } as Response)
  .mockImplementation(ok);                    // appels suivants : 200 simple
transport = new HttpTransport(queue, config, undefined, {
  fetchImpl: fetchImpl as unknown as typeof fetch, now,
});
```

Puis on affirme sur la signature EXACTE attendue (pas juste « un hex de 64 ») :

```typescript
const expected = await signMessage(roomKey, 'pid|sess-1|1700000000');
expect(headers['X-ExamSDK-Signature']).toBe(expected);
```

### 3.4 Les fixtures backend (`backend/tests/conftest.py`)

| Fixture | Fournit |
|---|---|
| `developer` / `other_developer` | 2 comptes développeurs (isolation multi-tenant) |
| `project` / `other_project` | 2 projets créés **via `ProjectService`** (vrais `pk_live_…`/`sk_live_…`) |
| `session` | une session d'examen ACTIVE du `project` |
| `make_event` | fabrique d'événements (write-once, idempotence) |
| `machine_headers` | en-têtes HMAC prêts à poster (`HTTP_X_EXAMSDK_PUBLIC_KEY` + signature) ; surchargeable : `machine_headers(message, public_key=…, signature=…)` |
| `now_epoch` | horodatage frais en secondes epoch |

Règle : **une fixture = une fabrique réutilisable**, jamais de données codées en dur
dispersées dans les tests.

---

## 4. Fichiers concernés (cartographie complète)

### 4.1 Backend

```
backend/
├── pytest.ini                      ← config globale (-ra -v, settings dev, testpaths)
├── tests/
│   ├── conftest.py                 ← fixtures partagées (§3.4)
│   ├── test_machine_api.py         ← HMAC + clés de chambre (sécurité, intégration API)
│   ├── test_tenant_isolation.py    ← isolation multi-tenant
│   ├── test_projects_api.py        ← API développeur + JWT
│   ├── test_jwt_signing_key.py     ← garde-fou RFC 7518
│   ├── test_risk_score.py          ← calcul du score de risque
│   ├── test_sdk_logs.py            ← journal SDK
│   ├── test_events.py / test_presenters.py / test_forms.py / …
│   └── load_simulation.py          ← SCRIPT de charge (pas pytest, backend allumé requis)
├── apps/
│   ├── core/hmac.py                ← sign_message, verify_signature, derive_session_key
│   ├── machine_api/authentication.py ← HMACAuthentication._signature_valid (2 clés)
│   ├── machine_api/views.py        ← sessions/, events/, logs/, exam-sessions/
│   └── events/catalog.py           ← CRITICAL_TYPES (DEVTOOLS_OPEN)
```

### 4.2 SDK

```
SDK/
├── vitest.config.ts                ← alias @/ → src/, environnement jsdom
├── tests/
│   ├── transport/HttpTransport.test.ts  ← cycle session + clé de chambre (§3.3)
│   ├── events/EventClassifier.test.ts   ← DEVTOOLS_OPEN critique
│   ├── config/SdkConfig.test.ts         ← validation live + pré-provisionné
│   ├── events/EventPipeline.test.ts     ← critical → sendNow immédiat
│   ├── diagnostics/Diagnostics.test.ts  ← heartbeat + journal
│   └── … (voir §2.2)
├── src/
│   ├── transport/HttpTransport.ts  ← signingKey(), sessionKey en mémoire
│   ├── transport/HmacAuth.ts       ← canoniques + deriveSessionKey (miroir backend)
│   ├── config/SdkConfig.ts         ← sessionKey + mode pré-provisionné
│   └── events/EventClassifier.ts   ← CRITICAL_TYPES
```

---

## 5. Commandes (par module et par scénario)

### 5.1 Backend — depuis `D:\Live_or_Die\TFC_realisation\realisations 2\backend`

```powershell
# --- Toute la suite (mode détaillé : 1 ligne par test, activé dans pytest.ini) ---
& ".\.venv\Scripts\python.exe" -m pytest

# --- Un seul fichier ---
& ".\.venv\Scripts\python.exe" -m pytest tests/test_machine_api.py        # sécurité HMAC
& ".\.venv\Scripts\python.exe" -m pytest tests/test_tenant_isolation.py   # multi-tenant
& ".\.venv\Scripts\python.exe" -m pytest tests/test_projects_api.py       # API développeur
& ".\.venv\Scripts\python.exe" -m pytest tests/test_jwt_signing_key.py    # garde-fou clé JWT

# --- Un seul test (par son nom complet) ---
& ".\.venv\Scripts\python.exe" -m pytest tests/test_machine_api.py::test_events_signed_with_room_key

# --- Filtrer par mot-clé (expression -k, insensible aux noms de fichiers) ---
& ".\.venv\Scripts\python.exe" -m pytest -k "room_key"        # tous les tests clés de chambre
& ".\.venv\Scripts\python.exe" -m pytest -k "not slow and machine"

# --- Arrêt à la première erreur (debug rapide) ---
& ".\.venv\Scripts\python.exe" -m pytest -x

# --- Afficher les print() et le détail complet des échecs ---
& ".\.venv\Scripts\python.exe" -m pytest -vv -s
```

### 5.2 Charge (backend allumé requis — port 8000)

```powershell
# 1) Allumer le serveur (autre terminal, depuis backend/) :
& ".\.venv\Scripts\python.exe" manage.py runserver

# 2) Créer un projet (dashboard http://localhost:8000) et récupérer ses 3 clés,
#    puis lancer la simulation — exemple palier 30 étudiants / 5 minutes :
& ".\.venv\Scripts\python.exe" tests\load_simulation.py `
  --students 30 --duration 300 `
  --base-url http://localhost:8000/api/v1/machine `
  --project-id "LE_UUID_DU_PROJET" `
  --public-key "pk_live_…" --secret-key "sk_live_…" `
  --exam-id "EXAM-SIM-1"

# Mode volume (25000 événements par session, lots de 500) :
#   ajouter --volume-events 25000 --volume-batch 500
```

> ⚠️ Les sessions créées portent des identifiants `sim-XXXX` : nettoyage de la base
> à prévoir après un gros run (sur demande uniquement).

### 5.3 SDK — depuis `D:\Live_or_Die\TFC_realisation\realisations 2\SDK`

```powershell
# --- Toute la suite (une passe) ---
npm test

# --- Mode watch : relance à chaque modification (développement) ---
npm run test:watch

# --- Un seul fichier ---
npx vitest run tests/transport/HttpTransport.test.ts
npx vitest run tests/events/EventClassifier.test.ts
npx vitest run tests/config/SdkConfig.test.ts

# --- Un seul test par son nom ---
npx vitest run -t "pré-provisionné"

# --- Détail nom par nom (comme le -v de pytest) ---
npx vitest run --reporter=verbose

# --- Vérification des types (à passer avant de dire « fini ») ---
npx tsc --noEmit
```

### 5.4 Les deux suites d'un coup (vérification finale avant commit)

```powershell
# Terminal 1 — backend
& ".\.venv\Scripts\python.exe" -m pytest
# Terminal 2 — SDK
npm test ; npx tsc --noEmit
```

---

## 6. Les ajouts du 14/11/2026 (clés à 2 niveaux + DevTools critique)

| Test | Fichier | Type | Il prouve que… |
|---|---|---|---|
| `test_session_create_returns_derived_session_key` | `test_machine_api.py` | intégration sécurité | l'initiation livre `session_key` = `HMAC(maîtresse, "session-key\|<id>")`, déterministe à la ré-ouverture |
| `test_events_signed_with_room_key` | `test_machine_api.py` | intégration sécurité | un lot signé UNIQUEMENT avec la clé de chambre est accepté (202) |
| `test_close_signed_with_room_key` | `test_machine_api.py` | intégration sécurité | la clôture se signe avec la clé de chambre |
| `test_foreign_room_key_is_401` | `test_machine_api.py` | sécurité (attaque) | la clé de chambre d'un autre projet ne valide rien (401) |
| `test_room_key_of_another_session_is_401` | `test_machine_api.py` | sécurité (attaque) | tentative de greffe sur une autre session → 401 |
| `test_jwt_signing_key_is_at_least_32_bytes` | `test_jwt_signing_key.py` | garde-fou config | clé JWT ≥ 32 octets (RFC 7518 §3.2) |
| DevTools critique (`EventClassifier`) | `EventClassifier.test.ts` | unitaire | `DEVTOOLS_OPEN` ∈ `CRITICAL_TYPES` → sévérité `critical` → envoi immédiat |
| capture `session_key` + signatures | `HttpTransport.test.ts` | intégration transport | les événements et la clôture sont signés avec la clé de chambre, la maîtresse ne sert qu'à l'initiation |
| compatibilité sans `session_key` | `HttpTransport.test.ts` | intégration transport | backend antérieur (pas de clé) → signature maîtresse, rien ne casse |
| mode pré-provisionné | `HttpTransport.test.ts` | intégration transport | `sessionId + sessionKey` du LMS → AUCUN appel réseau, tout signé avec la clé du LMS |
| validation pré-provisionné | `SdkConfig.test.ts` | unitaire config | `secretKey`/`examId`/`studentId` non requis si pré-provisionné ; `publicKey`/`projectId`/`apiUrl` toujours requis |

---

## 7. Bonnes pratiques et pièges (à lire avant d'écrire un test)

1. **La signature, c'est `HMAC(clé, message)` — jamais la clé elle-même.**
   Piège classique : passer la clé de chambre comme valeur d'en-tête `X-ExamSDK-Signature`
   (erreur commise puis corrigée dans `test_events_signed_with_room_key`). L'en-tête porte
   toujours la signature du MESSAGE.
2. **Temps constant et fraîcheur ne se testent pas « à la main »** : on teste le COMPORTEMENT
   (401 sur signature fausse / horodatage périmé), l'implémentation (`hmac.compare_digest`)
   est vérifiée par lecture du code.
3. **404, pas 403**, pour toute ressource d'un autre tenant (on ne révèle pas l'existence).
4. **Un test = un scénario** : pas de boucle « pour tous les cas » dans un test — sinon on ne
   sait plus QUEL cas a cassé.
5. **Ne jamais dépendre du réseau réel** ni de l'ordre des tests ; chaque test crée ses
   propres données (pytest-django isole chaque test dans une transaction).
6. **Un échec de canonique est un signal précieux** : quelqu'un a changé le contrat d'un côté
   sans l'autre. On ne « répare » jamais le test pour le faire passer — on arbitre le contrat.
7. **L'affichage détaillé est la config par défaut** (`pytest.ini` : `-ra -v`) — chaque test
   s'affiche nominalement, les échecs/sautés sont résumés en fin de run.
