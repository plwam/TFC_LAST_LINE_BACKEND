# Consignes pour l'agent de code — Règles opérationnelles et livrables

> **À lire en tout premier**, avant `00_PROJECT_OVERVIEW.md` et les fichiers de module. Ce document ne décrit pas l'architecture (elle est dans les autres fichiers) — il décrit **comment travailler** sur ce projet : ce qu'on attend de toi, ce que tu dois produire, et les règles à respecter sans exception.

---

## 1. Documents de référence — ordre de lecture obligatoire

| # | Fichier | Contenu |
| :--- | :--- | :--- |
| 1 | `05_AGENT_GUIDELINES.md` (ce fichier) | Règles de travail |
| 2 | `00_PROJECT_OVERVIEW.md` | Architecture globale, contrat d'événement, principes non négociables |
| 3 | `01_BACKEND.md` | Spécification Backend |
| 4 | `02_SDK.md` | Spécification SDK |
| 5 | `03_EXTENSION.md` | Spécification Extension |
| 6 | `04_TESTS.md` | Stratégie de tests |
| 7 | `06_FRONTEND_GUIDE.md` | Interface du tableau de bord Django (templates + Tailwind CDN), pages et contenus — à lire avant de toucher à `apps/dashboard/` ou aux surcharges allauth |

**Ne commence jamais à coder un module sans avoir lu son fichier de spec en entier, même si la tâche demandée semble petite.** Une fonction qui paraît isolée a presque toujours une conséquence sur un autre module (cf. §5).

---

## 2. Liste des livrables attendus

Ce projet n'est terminé que lorsque les livrables suivants existent, pas avant :

### 2.1 Code
- [ ] `backend/` — projet Django complet et exécutable (`docker-compose up` doit fonctionner de bout en bout)
- [ ] `sdk/` — package TypeScript buildable (`npm run build` produit les fichiers ESM/UMD/IIFE)
- [ ] `extension/` — extension Manifest V3 chargeable telle quelle dans Chrome (`chrome://extensions` → "Charger l'extension non empaquetée")
- [ ] `tests/` — suites de tests individuelles (backend, SDK, extension) et communes (E2E), toutes exécutables
- [ ] Frontend du tableau de bord (templates, composants, surcharges allauth, `static/`) — liste détaillée dans `06_FRONTEND_GUIDE.md` §15

### 2.2 Documentation de configuration (obligatoire, voir §6)
- [ ] `backend/SETUP.md`
- [ ] `sdk/SETUP.md`
- [ ] `extension/SETUP.md`
- [ ] `tests/SETUP.md`
- [ ] `README.md` à la racine, qui renvoie vers les quatre précédents

### 2.3 Ce qui n'est PAS un livrable de ce projet
- Une interface publicitaire/marketing pour le service (hors périmètre du mémoire)
- Une application mobile réelle (seule l'API JWT qui la permettra plus tard est à livrer, pas l'app elle-même)
- Tout module, dépendance ou fonctionnalité non mentionné dans les fichiers 00 à 04

---

## 3. Règle n°1 — Ne jamais sortir du périmètre du projet

Avant chaque action (créer un fichier, ajouter une dépendance, choisir une techno), vérifie :

1. **Est-ce que c'est écrit dans un des fichiers 00 à 04 ?** Si oui, tu peux avancer.
2. **Est-ce une conséquence directe et nécessaire de ce qui est écrit** (ex. un fichier de migration Django n'est pas nommé explicitement mais découle forcément d'un modèle décrit) ? Si oui, tu peux avancer.
3. **Sinon → tu t'arrêtes et tu demandes**, avant d'écrire le code. Tu n'improvises jamais une fonctionnalité, une librairie ou un choix d'architecture qui n'a pas été validé, même si ça te semble une bonne idée ou une amélioration évidente.

**Exemples concrets de dérive à éviter :**
- Ajouter un système de notifications push "parce que ce serait utile" → non prévu, ne pas faire.
- Remplacer MySQL par PostgreSQL "parce que plus adapté à tel besoin" → décision déjà tranchée, ne pas revenir dessus sans validation explicite.
- Ajouter une dépendance non mentionnée pour résoudre un problème → vérifier d'abord si la solution attendue est déjà décrite autrement dans les specs.

**Si tu repères une incohérence entre deux fichiers de spec**, ou entre une spec et une contrainte technique réelle que tu découvres en codant (ex. une limite d'API que la spec ignorait) : **signale-le explicitement plutôt que de trancher silencieusement dans un sens ou l'autre.**

---

## 4. Règle n°2 — Commentaires de code obligatoires, avec justification et exemple

**Chaque bloc de code non trivial doit être commenté directement au-dessus ou à l'intérieur, expliquant :**
1. **Ce qu'il fait** (brièvement — le code le montre déjà, pas la peine de répéter ligne à ligne)
2. **Pourquoi ce choix précis** (c'est la partie qui manque le plus souvent et qui a le plus de valeur)
3. **Un exemple concret** quand la logique n'est pas évidente à l'œil (entrée → sortie, ou un cas limite)

### Mauvais commentaire (à ne jamais faire)
```typescript
// Incrémente le compteur
counter++;
```
Ça ne dit rien que le code ne dit déjà — inutile.

### Bon commentaire (attendu systématiquement)
```typescript
// On revérifie la signature en temps constant (hmac.compare_digest côté Python, ici l'équivalent JS)
// plutôt qu'avec === : une comparaison naïve s'arrête au premier caractère différent, ce qui permet
// à un attaquant de deviner la signature octet par octet en mesurant le temps de réponse.
// Exemple : comparer "abc123" à "abc999" est plus lent que "xyz123" à "abc999" avec ===,
// ce qui fuit de l'information — timingSafeEqual élimine cette différence de timing.
if (!timingSafeEqual(receivedSignature, expectedSignature)) {
  throw new AuthenticationError('Invalid signature');
}
```

### Où ce niveau de détail est non négociable
- Tout ce qui touche à la sécurité (HMAC, validation d'origine `postMessage`, isolation multi-tenant)
- Toute logique avec des seuils/constantes qui semblent arbitraires (`gazeAwayThresholdMs`, `headTurnCountThreshold`, etc.) — expliquer pourquoi cette valeur et pas une autre
- Tout contournement d'une limite technique (ex. `chrome.alarms` au lieu de `setInterval`) — expliquer le piège évité
- Toute fonction qui existe à cause d'une décision prise en cours de conversation plutôt qu'une évidence technique

### Où un commentaire léger suffit
- Code auto-descriptif (un getter simple, une fonction utilitaire triviale) — ne pas sur-commenter non plus, un commentaire qui ne dit rien de plus que le nom de la fonction est du bruit.

---

## 5. Règle n°3 — Garder une vue d'ensemble à chaque étape, ne jamais coder un module en silo

Avant de modifier un fichier dans un module, vérifie systématiquement :

1. **Ce fichier fait-il partie du contrat partagé ?** (schéma d'événement, `EventType`, protocole `postMessage`) → si tu le modifies dans un module, tu dois le refléter dans les deux autres **dans le même lot de travail**, jamais "je ferai le reste plus tard".
2. **Une modification backend change-t-elle un endpoint que le SDK ou l'extension appelle ?** → vérifie `02_SDK.md`/`03_EXTENSION.md` avant de changer une signature d'API.
3. **Avant de terminer une session de travail sur un module, relis `00_PROJECT_OVERVIEW.md` §7 et §8** (contrat d'événement, mécanismes transversaux) pour vérifier que rien de ce que tu viens de faire ne les contredit.

**Exemple concret de ce qu'il ne faut pas faire** : ajouter un nouveau champ `EventType` côté SDK sans l'ajouter aux choix du modèle `Event` côté backend — le test `contract-check` de `04_TESTS.md` §4.1 est fait pour attraper ce genre d'erreur, mais il vaut mieux ne jamais la commettre plutôt que de compter sur le test pour la détecter après coup.

**Si une tâche demandée impacte plusieurs modules**, traite-les dans le même lot de travail plutôt que d'en faire un et d'oublier les autres — ou, si ce n'est pas possible en une seule fois, **écris explicitement ce qui reste à faire côté des autres modules** avant de considérer la tâche terminée.

---

## 6. Règle n°4 — Toujours documenter la configuration nécessaire

Pour chaque module, un fichier `SETUP.md` doit exister et rester à jour, contenant :

1. **Prérequis** (versions de Node/Python, comptes externes nécessaires)
2. **Variables d'environnement**, une par une, avec :
   - à quoi elle sert
   - comment l'obtenir concrètement (pas juste son nom)
   - une valeur d'exemple pour le développement local (jamais une vraie clé secrète)
3. **Étapes d'installation**, dans l'ordre, testées (pas supposées)
4. **Étapes de déploiement**, y compris pour l'hébergement externe (voir §7 pour les choix retenus)
5. **Comment vérifier que ça fonctionne** (une commande ou une URL à tester après installation)

### Exemple attendu pour une variable d'environnement (niveau de détail à respecter)
```markdown
### FIELD_ENCRYPTION_KEY
Clé utilisée pour chiffrer `secret_key` au repos en base de données (voir 01_BACKEND.md §12).
À générer une fois avec : `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
Ne jamais regénérer cette clé après la mise en production — toutes les `secret_key` existantes deviendraient illisibles.
Exemple (dev local uniquement, à ne jamais utiliser en production) : `FIELD_ENCRYPTION_KEY=dGVzdC1rZXktbmUtcGFzLXV0aWxpc2VyLWVuLXByb2Q=`
```
Pas juste `FIELD_ENCRYPTION_KEY=<ta clé>` sans explication — l'agent qui lira ce fichier plus tard (toi dans une session future, ou un autre agent) doit pouvoir agir sans deviner.

---

## 7. Hébergement et services externes — choix figés, à ne pas réinterpréter

| Besoin | Solution retenue | Règle |
| :--- | :--- | :--- |
| Hébergement du SDK (code JS) et des poids de modèles IA | **Cloudflare Pages** (gratuit, prototype) | Limite de 25 Mio par fichier — vérifier que chaque fichier de poids de modèle respecte cette limite avant upload |
| Si un fichier de poids dépasse 25 Mio | **GitHub Releases** (jusqu'à 2 Go/fichier) en repli, uniquement pour ce fichier précis | Ne pas migrer tout le reste vers GitHub Releases par simplicité — seulement le(s) fichier(s) concerné(s) |
| Base de données | MySQL 8+ | Ne pas proposer PostgreSQL même si "plus adapté" à une fonctionnalité future — décision figée |
| Authentification sociale | Google + GitHub via `django-allauth` | Ne pas ajouter d'autre fournisseur (Facebook, Microsoft...) sans validation explicite |
| Style du dashboard | Tailwind CSS via CDN (Play CDN, version épinglée), prototype uniquement | Ne pas ajouter de framework JS (Alpine, HTMX, React, Vue) ni de librairie de composants sans validation ; migrer vers un CSS compilé avant toute mise en production (`06_FRONTEND_GUIDE.md` §2.4) |

**Toute introduction d'un nouveau service externe non listé ci-dessus (autre CDN, autre base de données, autre fournisseur d'auth, service de monitoring tiers, etc.) doit être validée avant implémentation — ne jamais l'ajouter silencieusement même si ça résout un problème rencontré en cours de route.**

---

## 8. Checklist avant de considérer une tâche terminée

- [ ] Le code respecte la spec du fichier de module correspondant (00 à 04) — pas d'improvisation non validée (§3)
- [ ] Chaque bloc de code non trivial est commenté selon le niveau attendu en §4
- [ ] Si la tâche touchait un contrat partagé (événement, protocole, endpoint), les autres modules concernés ont été mis à jour ou le reste-à-faire est explicitement noté (§5)
- [ ] Le `SETUP.md` du module concerné est à jour si une nouvelle variable d'environnement ou étape d'installation a été introduite (§6)
- [ ] Aucun nouveau service externe non listé en §7 n'a été introduit sans validation
- [ ] Les tests correspondants (`04_TESTS.md`) existent pour le code ajouté, pas seulement prévus pour plus tard

---

## 9. En cas de doute

Une ambiguïté dans les specs, une contrainte technique imprévue, ou une tentation de dévier du périmètre : **signale-le et demande, plutôt que de trancher seul et de continuer**. Une question posée à temps coûte moins cher qu'un module entier à refaire parce qu'une hypothèse silencieuse s'est avérée fausse.
