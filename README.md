# CTF Destroyer

Orchestrateur agentique pour challenges CTF. Il prépare un workspace par challenge, route vers un skill adapté, lance un worker (`mock`, `codex`, `claude`), garde une mémoire de reprise locale, puis boucle jusqu'au flag ou jusqu'à la limite d'essais.

## Ce que fait le projet

- normalise des descriptions de challenge hétérogènes
- crée un workspace isolé sous `.challenges/<slug>-<hash>/`
- copie les artefacts locaux et télécharge les artefacts HTTP(S)
- route vers un skill selon la catégorie
- exécute des workers spécialisés avec un contrat de sortie commun
- conserve l'historique, une mémoire de handoff et un `writeup.md`
- peut publier le suivi dans un fil Discord dédié

## Pré-requis

- Python `3.11+`
- `codex` installé et authentifié pour le backend `codex`
- `claude` installé et authentifié pour le backend `claude`

Le projet tourne aussi avec Python `3.14`, mais un setup plus propre reste `3.12` ou `3.13`.

## Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Usage rapide

Run de test sans LLM:

```bash
ctf-orchestrator \
  --challenge-file examples/evaluative.json \
  --backend-sequence mock \
  --max-attempts 2
```

Run avec alternance de providers:

```bash
ctf-orchestrator \
  --challenge-file examples/forbidden-fruit.json \
  --backend-sequence claude,codex \
  --max-attempts 10
```

Run avec budget worker plus court:

```bash
WORKER_TIMEOUT_SECONDS=300 \
WORKER_PERMISSION_MODE=default \
ctf-orchestrator \
  --challenge-file examples/evaluative.json \
  --backend-sequence codex
```

Importer un challenge depuis un texte collé:

```bash
pbpaste | ctf-import - --output examples/imported.json --review
```

Importer une page simple protégée par cookie de session:

```bash
ctf-import \
  "https://ctf.example.com/challenges/noise-cheap" \
  --session-cookie "abc123" \
  --output examples/noise-cheap.json \
  --review
```

Importer un challenge CTFd conteneurisé en démarrant l'instance avant l'export:

```bash
ctf-import \
  --session-cookie "abc123" \
  "https://ctf.example.com/challenges" \
  --challenge "Glitch The Wired" \
  --start-instance \
  --output examples/glitch-the-wired.json
```

Lister plusieurs challenges détectés sur une même source:

```bash
ctf-import --input-file board.txt --list
ctf-import --input-file board.txt --challenge "Noise Cheap" --stdout
```

## Format d'entrée

Le CLI sait normaliser les champs suivants:

- `title`, `name`, `challenge_name`
- `description`, `scenario`, `challenge_scenario`, `challenge_text`
- `category`, `category_hint`
- `files`, `artifacts`, `artifact_paths`
- `target_host` ou `ip` + `port`

Tous les autres champs sont conservés dans `challenge_metadata`.

Exemple minimal:

```json
{
  "title": "Forbidden Fruit",
  "category": "crypto",
  "description": "AES-GCM misuse challenge.",
  "target_host": "aes.cryptohack.org:443",
  "files": [
    "https://aes.cryptohack.org/forbidden_fruit/",
    "https://toadstyle.org/cryptopals/63.txt"
  ],
  "operator_hint": "Exploit AES-GCM nonce reuse. Avoid brute force."
}
```

Exemples fournis:

- [examples/evaluative.json](/Users/tj/Documents/CTF-Destroyer/examples/evaluative.json)
- [examples/bruce-schneiers-password-part-2.json](/Users/tj/Documents/CTF-Destroyer/examples/bruce-schneiers-password-part-2.json)
- [examples/forbidden-fruit.json](/Users/tj/Documents/CTF-Destroyer/examples/forbidden-fruit.json)

## Import de challenges

`ctf-import` convertit une source brute vers le format JSON du projet.

Ce que la V1 couvre:

- texte collé sur `stdin`
- fichier texte local via `--input-file`
- URL HTML simples
- détection de plusieurs challenges dans une même source
- sélection d'un challenge via `--challenge`
- cookie de session brut via `--session-cookie` ou `--cookie-file`
- import CTFd via API quand la board est accessible
- récupération de `target_host` pour un challenge CTFd conteneurisé si l'instance est déjà démarrée dans l'UI
- démarrage d'une instance CTFd conteneurisée via `--start-instance` quand la page source expose le `csrfNonce`

Flags principaux:

- `ctf-import <url>`
- `ctf-import -`
- `--input-file`
- `--output`
- `--stdout`
- `--review`
- `--list`
- `--challenge`
- `--session-cookie`
- `--cookie-file`
- `--start-instance`

`--session-cookie` accepte soit une valeur nue de session Flask/CTFd, soit un header `Cookie` complet. Si tu lui passes seulement un token, `ctf-import` l'envoie comme `session=<token>`.

`--start-instance` ne s'applique qu'à l'import CTFd. Le CLI réutilise d'abord l'instance courante si elle correspond déjà au challenge sélectionné; sinon il envoie le POST de démarrage CTFd puis poll `/api/v1/containers/current` pour récupérer `access` et remplir `target_host`.

Si `--start-instance` a été demandé et qu'aucun `target_host` n'a pu être récupéré, `ctf-import` échoue explicitement avec un code de retour non nul et n'écrit pas un JSON inutilisable par défaut.

`ctf-orchestrator` refuse aussi de démarrer un worker sur un challenge importé qui indique explicitement un échec d'accès d'instance après `--start-instance`.

Limites actuelles de `ctf-import`:

- pas encore de navigation browser ou clics dynamiques
- pas encore d'extracteurs dédiés CryptoHack/CTFd
- pas encore de suivi guidé de liens externes type SharePoint
- pas encore de sélection par identifiant de challenge

## Workspace et reprise

Chaque challenge vit dans un dossier dédié:

```text
.challenges/<slug>-<hash>/
```

Fichiers utiles:

- `challenge.json`: manifeste normalisé
- `artifacts/`: fichiers copiés ou téléchargés
- `.runs/attempt-history.json`: historique des tentatives
- `.runs/working-memory.json`: mémoire de reprise
- `writeup.md`: writeup généré après résolution par un worker de rédaction dédié quand un backend réel est disponible, avec fallback local heuristique
- `.discord-thread.json`: binding Discord local si l'intégration est activée

La reprise lit automatiquement l'historique et la mémoire locale avant un nouveau run.

## Workers et config

Les workers `codex` et `claude` partagent la même base de configuration côté orchestrateur:

- même prompt métier
- même schéma de sortie structuré
- même ordre via `--backend-sequence`
- même famille de variables `WORKER_*`
- même observabilité des commandes au niveau du projet

Variables utiles:

- `WORKER_TIMEOUT_SECONDS`
- `WORKER_PERMISSION_MODE`
- `WORKER_STREAM_EVENTS`
- `CODEX_MODEL`
- `CODEX_SANDBOX`
- `CODEX_APPROVAL_POLICY`
- `CODEX_EXTRA_ARGS`
- `CLAUDE_MODEL`
- `CLAUDE_EXTRA_ARGS`

Les variables `WORKER_*` sont à privilégier pour une config provider-agnostic. Les variables `CODEX_*` et `CLAUDE_*` servent d'override spécifique provider.

Valeurs possibles:

- `WORKER_TIMEOUT_SECONDS`: entier en secondes. Défaut `1800`.
- `WORKER_PERMISSION_MODE`: mode provider-agnostic.
  Valeurs recommandées:
  `default`, `safe`, `never`, `dontAsk`, `dont-ask`, `dont_ask`
  `auto`, `on-request`, `on_request`
  `plan`, `readonly`, `read-only`, `read_only`, `untrusted`
  `bypassPermissions`, `bypass_permissions`, `danger-full-access`, `danger_full_access`, `unrestricted`
  `acceptEdits`, `accept_edits` pour Claude uniquement
- `WORKER_STREAM_EVENTS`: booléen. `0`, `false`, `no`, `off` désactivent le streaming. Toute autre valeur non vide l'active. Défaut `true`.
- `CODEX_MODEL`: nom de modèle passé à `codex -m`.
- `CODEX_SANDBOX`: `read-only`, `workspace-write`, `danger-full-access`.
  Alias acceptés par le projet: `seatbelt`, `sandbox`, `workspace` -> `workspace-write`.
  Toute autre valeur retombe sur `workspace-write`.
- `CODEX_APPROVAL_POLICY`: chaîne transmise au CLI Codex. En pratique, les valeurs utiles ici sont `never`, `on-request`, `untrusted`.
- `CODEX_EXTRA_ARGS`: arguments additionnels passés tels quels à `codex`, sous forme de chaîne shell splittée.
- `CLAUDE_MODEL`: nom de modèle passé à `claude --model`.
- `CLAUDE_PERMISSION_MODE`: chaîne transmise au CLI Claude.
  Valeurs utilisées par le projet: `default`, `dontAsk`, `auto`, `plan`, `bypassPermissions`, `acceptEdits`.
- `CLAUDE_EXTRA_ARGS`: arguments additionnels passés tels quels à `claude`, sous forme de chaîne shell splittée.

Mapping de `WORKER_PERMISSION_MODE`:

- `default`, `safe`, `never`, `dontAsk` -> Codex `workspace-write` + `never`, Claude `dontAsk`
- `auto`, `on-request` -> Codex `workspace-write` + `on-request`, Claude `auto`
- `plan`, `readonly`, `read-only`, `untrusted` -> Codex `read-only` + `untrusted`, Claude `plan`
- `bypassPermissions`, `danger-full-access`, `unrestricted` -> Codex `danger-full-access` + `never`, Claude `bypassPermissions`
- `acceptEdits` -> Claude `acceptEdits`, mais Codex retombe sur le mode sûr par défaut

## Discord

Si `DISCORD_BOT_TOKEN` et `DISCORD_PARENT_CHANNEL_ID` sont définis, le CLI crée ou réutilise un fil Discord par challenge et y publie:

- le message initial
- le routage
- chaque tentative
- le résultat final
- le contenu de `writeup.md` après un solve réussi

Exemple:

```bash
export DISCORD_BOT_TOKEN=...
export DISCORD_PARENT_CHANNEL_ID=123456789012345678

ctf-orchestrator \
  --challenge-file examples/forbidden-fruit.json \
  --backend-sequence claude,codex
```

Flags associés:

- `--discord-bot-token`
- `--discord-parent-channel-id`
- `--discord-auto-archive-duration`
- `--env-file`

Variables d'environnement Discord:

- `DISCORD_BOT_TOKEN`: token du bot Discord
- `DISCORD_PARENT_CHANNEL_ID`: ID du salon parent qui héberge les threads
- `DISCORD_AUTO_ARCHIVE_DURATION`: une des valeurs `60`, `1440`, `4320`, `10080`

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Limites actuelles

- pas encore de parallélisme multi-challenges
- pas encore de planificateur global
- pas encore de persistance distante
- pas encore d'UI live dédiée
