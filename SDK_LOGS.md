# Journal SDK — ce que le SDK doit **obligatoirement** fournir

> Ce document décrit le contrat minimal que le SDK (ou l'agent) doit respecter pour alimenter
> la rubrique **« Journal SDK »** du dashboard ExamSDK : l'onglet du projet où le développeur
> voit, en temps réel, **si son SDK fonctionne ou non**.

---

## 1. À quoi ça sert

Le développeur ne peut pas se douter que son SDK est tombé (caméra refusée, script bloqué,
onglet fermé, erreur JavaScript…). Le journal répond à trois questions :

- **Le SDK tourne-t-il ?** → un signal de vie périodique (*heartbeat*).
- **Signale-t-il un problème ?** → des messages de journal (*logs*) avec un niveau.
- **Depuis quand / à quelle heure ?** → chaque entrée est horodatée à sa **réception** serveur.

ExamSDK en déduit un état, affiché dans la **Vue d'ensemble** et en tête de l'onglet :

| État affiché | Signification | Règle serveur |
|---|---|---|
| **En ligne** | Le SDK est vivant et ne signale rien. | Un heartbeat reçu dans la fenêtre, aucune erreur récente. |
| **Dégradé** | Le SDK est vivant **mais** signale une erreur. | Un heartbeat récent **et** au moins un `level=error` récent. |
| **Hors ligne** | Le SDK ne tourne plus (ou ne joint plus le serveur). | **Aucun** heartbeat dans la fenêtre. |

> ⚠️ L'état est calculé **exclusivement** à partir de l'horodatage de réception côté serveur
> (`received_at`) : le SDK ne peut donc pas « déclarer » qu'il est en ligne. **Seul le heartbeat
> prouve la vie.** Un SDK qui n'envoie que des logs, sans heartbeat, est affiché *Hors ligne*.

---

## 2. Prérequis

1. **Les clés du projet** : `public_key` (identifie le projet) et `secret_key` (signe les appels).
   Elles sont visibles dans l'onglet **Clés API** du projet.
2. **Une horloge raisonnablement exacte** : la signature contient un `issued_at` (epoch secondes)
   qui doit être proche de l'heure serveur (fenêtre de tolérance, 5 min par défaut).
3. **Un accès réseau sortant** vers l'API ExamSDK (`POST /api/v1/machine/logs/`).

> 🔒 **La clé secrète ne doit JAMAIS être placée dans la page d'examen** (navigateur étudiant).
> Si le SDK s'exécute dans le navigateur, il doit **relayer** ses entrées vers un composant de
> confiance (votre serveur d'examen ou votre LMS) qui signe et appelle ExamSDK. Un SDK exécuté
> côté serveur peut signer directement. *Voir §7 pour un squelette serveur.*

---

## 3. L'endpoint

```
POST /api/v1/machine/logs/
```

### En-têtes (obligatoires)

| En-tête | Contenu |
|---|---|
| `X-ExamSDK-Public-Key` | La `public_key` de votre projet. |
| `X-ExamSDK-Signature` | HMAC-SHA256 hexadécimal calculé avec la `secret_key`. |
| `Content-Type` | `application/json` |

### Chaîne canonique à signer (spécifique au journal)

```
project_id|sdk-logs|issued_at
```

- `project_id` : l'identifiant **UUID** du projet (pas la clé publique).
- `sdk-logs` : constante littérale (permet de distinguer cette surface des sessions/événements).
- `issued_at` : le même entier que dans le corps JSON.

> Cette canonique est **différente** de celle des sessions et des événements : un heartbeat peut
> partir *avant* l'ouverture d'une session, il n'y a donc pas de `session_id` à signer.

### Corps JSON

```json
{
  "issued_at": 1729000200,
  "session_id": "6f1c0f2a-3b6e-4c1a-9f2e-1a2b3c4d5e6f",
  "logs": [
    {
      "kind": "heartbeat",
      "level": "info",
      "sdk_version": "1.2.0",
      "occurred_at": "2024-10-15T12:30:00Z"
    },
    {
      "kind": "log",
      "level": "error",
      "message": "Caméra indisponible (NotReadableError).",
      "sdk_version": "1.2.0",
      "context": { "device": "webcam", "attempt": 3 },
      "occurred_at": "2024-10-15T12:30:02Z"
    }
  ]
}
```

| Champ | Portée | Obligatoire | Détails |
|---|---|---|---|
| `issued_at` | racine | **oui** | Epoch secondes ; sert à la signature et à l'anti-rejeu. |
| `session_id` | racine | non | UUID d'une session **du même projet** ; rattache le lot à une passation. |
| `logs` | racine | **oui** | Tableau, **1 à 200** entrées. |
| `logs[].kind` | entrée | non | `heartbeat` (signal de vie, par défaut `log`). |
| `logs[].level` | entrée | non | `debug` \| `info` \| `warning` \| `error` (défaut `info`). |
| `logs[].message` | entrée | non | Texte lisible (vide admis pour un heartbeat). |
| `logs[].sdk_version` | entrée | non | Version du SDK émetteur. |
| `logs[].context` | entrée | non | Objet JSON libre (diagnostic). **Jamais une donnée personnelle** (§5). |
| `logs[].occurred_at` | entrée | non | Horodatage côté SDK (ISO 8601). Défaut : heure serveur. |

### Réponse

```json
{ "accepted": 2 }
```

`HTTP 202` si le lot est accepté.

| Code | Cas |
|---|---|
| `202` | Lot accepté. |
| `400` | Corps invalide (lot vide, plus de 200 entrées, niveau/type inconnu…). |
| `401` | Signature absente/invalide, `issued_at` manquant, expiré, ou **projet inactif**. |
| `404` | `session_id` fourni mais introuvable dans **votre** projet (jamais celui d'un autre). |

> Un projet **suspendu / désactivé / archivé** reçoit `401` : ses clés ne valident plus rien.
> Le SDK doit alors **cesser poliment** d'envoyer (avec repli exponentiel) plutôt que marteler.

---

## 4. Exigences obligatoires (checklist d'implémentation)

Le journal ne fonctionne **que** si les points suivants sont respectés.

- [ ] **E1 — Signature HMAC.** Chaque appel porte les deux en-têtes et la canonique
      `project_id|sdk-logs|issued_at`. `issued_at` est recalculé à **chaque** envoi.
- [ ] **E2 — Heartbeat périodique.** Le SDK envoie un `kind=heartbeat` :
  - **au démarrage** (prouve que le script s'est chargé) ;
  - **puis à intervalle régulier** (voir §5) ;
  - **à chaque reprise** (retour d'onglet au premier plan, retour du réseau).
- [ ] **E3 — Capture des erreurs.** Un gestionnaire global (`window.onerror`,
      `unhandledrejection`, erreurs de permissions caméra/micro) envoie un `level=error`
      avec un `message` et un `context` utiles.
- [ ] **E4 — Journal de cycle de vie.** Émettre au moins : *démarrage* (`info`), *arrêt* (`info`),
      *permission refusée* (`warning`), *erreur fatale* (`error`).
- [ ] **E5 — Contexte & version.** Renseigner `sdk_version` sur chaque entrée, et un `context`
      minimal (nom du module, état des permissions…).
- [ ] **E6 — Rattachement session (recommandé).** Fournir `session_id` pour corréler les entrées
      avec une passation.
- [ ] **E7 — Robustesse réseau.** Regrouper les entrées en lots, réessayer avec un **repli
      exponentiel**, et **ne jamais bloquer** l'épreuve si l'envoi échoue.
- [ ] **E8 — Minimisation.** `message` et `context` ne contiennent **aucune donnée personnelle**
      (pas de nom, e-mail, réponse de l'étudiant). Uniquement du diagnostic technique.

---

## 5. Cadence du heartbeat et fenêtre de surveillance

| Paramètre | Valeur |
|---|---|
| Fenêtre serveur (`SDK_HEARTBEAT_WINDOW_SECONDS`) | **120 s** (réglable par le déploiement) |
| Cadence recommandée du SDK | **30 à 60 s** |

**Règle :** la cadence du heartbeat doit être **strictement inférieure** à la fenêtre (viser la
moitié ou le tiers). Sinon un SDK pourtant vivant sera affiché *Hors ligne* entre deux battements.

> 🧠 Le navigateur **ralentit** les minuteurs d'un onglet en arrière-plan (`setInterval` throttlé).
> Un SDK robuste envoie donc aussi un heartbeat sur les événements `visibilitychange` (retour au
> premier plan) et `online` (réseau rétabli), plutôt que de se fier au seul minuteur.

---

## 6. Exemple minimal (navigateur → votre serveur)

Côté navigateur : **collecter et relayer**, jamais signer.

```javascript
// sdk-logs-agent.js — le navigateur NE détient PAS la clé secrète.
const RELAY = "/api/examsdk/logs"; // votre serveur de confiance (relais signant)

function push(entries) {
  // fire-and-forget : on ne bloque jamais l'épreuve.
  fetch(RELAY, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: window.__examSessionId || null, logs: entries }),
    keepalive: true,
  }).catch(() => {/* renvoyé au prochain cycle */});
}

// E2 — heartbeat initial + périodique + sur reprise.
const HEARTBEAT_MS = 45000;
const beat = () => push([{ kind: "heartbeat", level: "info", sdk_version: "1.2.0" }]);
beat();
setInterval(beat, HEARTBEAT_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) beat(); });
window.addEventListener("online", beat);

// E3 — erreurs globales.
window.addEventListener("error", (e) =>
  push([{ kind: "log", level: "error", sdk_version: "1.2.0",
          message: String(e.message || "Erreur inconnue"),
          context: { source: "window.error" } }]));
window.addEventListener("unhandledrejection", (e) =>
  push([{ kind: "log", level: "error", sdk_version: "1.2.0",
          message: String((e.reason && e.reason.message) || e.reason),
          context: { source: "unhandledrejection" } }]));
```

---

## 7. Exemple serveur (relais signant)

Côté serveur de confiance : signer et appeler ExamSDK.

```python
import hashlib, hmac, time, json, urllib.request

EXAMSDK_BASE = "https://api.examsdk.example"
PROJECT_ID   = "3c8e1f2a-9b47-4d0e-8a11-2f6c9d4b7e01"  # UUID du projet
PUBLIC_KEY   = "pk_live_9f2c7a1b4e..."
SECRET_KEY   = "sk_live_..."                            # jamais envoyée au navigateur

def send_logs(logs, session_id=None):
    issued_at = int(time.time())
    canonical = f"{PROJECT_ID}|sdk-logs|{issued_at}"
    signature = hmac.new(SECRET_KEY.encode(), canonical.encode(), hashlib.sha256).hexdigest()

    body = {"issued_at": issued_at, "logs": logs}
    if session_id:
        body["session_id"] = session_id

    request = urllib.request.Request(
        f"{EXAMSDK_BASE}/api/v1/machine/logs/",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-ExamSDK-Public-Key": PUBLIC_KEY,
            "X-ExamSDK-Signature": signature,
        },
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return response.status, json.loads(response.read())

send_logs([
    {"kind": "heartbeat", "level": "info", "sdk_version": "1.2.0"},
    {"kind": "log", "level": "warning", "message": "Micro indisponible.",
     "context": {"device": "microphone"}},
])
```

---

## 8. Dépannage

| Symptôme dans le dashboard | Cause probable | Correctif SDK |
|---|---|---|
| Toujours **Hors ligne** | Aucun heartbeat, ou cadence > fenêtre. | E2 : ajouter/accelerer le heartbeat (§5). |
| **Hors ligne** alors que le SDK tourne | Onglet en arrière-plan (minuteur throttlé). | Envoyer un heartbeat sur `visibilitychange` / `online`. |
| Toujours **Dégradé** | Des erreurs sont journalisées en boucle. | Corriger la cause, puis vérifier le `context`. |
| Rien n'apparaît du tout | `401` (signature/`issued_at`) ou `404` (`session_id`). | E1 : revoir la canonique et la fraîcheur de `issued_at`. |
| Apparition en double | `issued_at`/lot rejoué. | Dédupliquer côté agent avant envoi. |

---

## 9. Référence rapide

```
POST /api/v1/machine/logs/
X-ExamSDK-Public-Key: pk_live_...
X-ExamSDK-Signature:  hmac_sha256(secret, "project_id|sdk-logs|issued_at")

Body : { issued_at, session_id?, logs: [ { kind, level, message, sdk_version, context, occurred_at } ] }
Réponse : 202 { "accepted": N }
États dérivés : En ligne (heartbeat frais) · Dégradé (heartbeat frais + error) · Hors ligne (pas de heartbeat)
Fenêtre : SDK_HEARTBEAT_WINDOW_SECONDS (défaut 120 s) — heartbeat recommandé toutes les 30–60 s.
```
