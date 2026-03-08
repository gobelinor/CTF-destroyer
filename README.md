# CTF Destroyer

PoC d'orchestration agentique pour challenges CTF.

Le projet utilise `LangGraph` comme orchestrateur et lance des workers spécialisés en subprocess, avec un focus actuel sur `codex`. L'objectif est simple: prendre un challenge, préparer un workspace isolé, choisir le bon skill, faire travailler un worker, tracer ce qu'il exécute, puis boucler jusqu'au flag ou jusqu'à une limite d'essais.

## État du projet

Le tool est encore un PoC, mais il fait déjà les choses suivantes:

- normalisation d'entrées challenge hétérogènes
- workspace dédié par challenge
- copie locale des artefacts
- routage vers un skill CTF par catégorie
- exécution de workers `mock`, `codex`, `claude`
- boucle orchestrateur `route -> specialist -> evaluate`
- capture des commandes et des sorties du worker
- streaming temps réel des événements `codex --json`

Ce n'est pas encore un orchestrateur multi-challenges complet.

## Fonctionnement

Cycle d'un run:

1. le CLI charge un challenge JSON ou des arguments directs
2. le challenge est normalisé
3. un workspace local est créé sous `.challenges/<slug>-<hash>/`
4. les artefacts sont copiés dans `artifacts/`
5. le routeur choisit un skill spécialisé
6. le worker sélectionné est lancé dans le workspace du challenge
7. l'orchestrateur évalue le résultat et décide de stopper ou de relancer

Le graphe LangGraph actuel est volontairement minimal:

```text
START
  -> route
  -> run_specialist
  -> evaluate
  -> END | run_specialist
```

## Structure

```text
ctf_destroyer/
  cli.py         # point d'entrée
  graph.py       # graphe LangGraph
  skills.py      # chargement + routage des skills
  workers.py     # workers mock/codex/claude
  workspace.py   # staging du workspace challenge
skills/
  ...            # skills CTF locaux
examples/
  evaluative.json
tests/
  ...
```

## Pré-requis

- Python `3.11+`
- `codex` installé et authentifié pour utiliser le backend `codex`
- `claude` installé et authentifié pour utiliser le backend `claude`

Le projet tourne ici avec Python `3.14`, mais `langchain-core` émet un warning. Pour un setup plus propre, viser Python `3.12` ou `3.13`.

## Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Utilisation rapide

Run local sans LLM:

```bash
ctf-orchestrator \
  --challenge-file examples/evaluative.json \
  --backend-sequence mock \
  --max-attempts 2
```

Run avec `codex`:

```bash
CODEX_TIMEOUT_SECONDS=120 \
ctf-orchestrator \
  --challenge-file examples/evaluative.json \
  --backend-sequence codex \
  --max-attempts 1
```

Run avec fallback `codex -> claude`:

```bash
ctf-orchestrator \
  --challenge-file examples/evaluative.json \
  --backend-sequence codex,claude \
  --max-attempts 4
```

## Format d'entrée

Le CLI sait normaliser les champs suivants:

- `title`, `name`, `challenge_name`
- `description`, `scenario`, `challenge_scenario`, `challenge_text`
- `category`, `category_hint`
- `files`, `artifacts`, `artifact_paths`
- `target_host` ou `ip` + `port`

Exemple:

```json
{
  "title": "Evaluative",
  "category": "misc",
  "description": "A rogue bot is malfunctioning, generating cryptic sequences that control secure data vaults.",
  "target_host": "154.57.164.64:31748",
  "difficulty": "Very Easy",
  "points": 10,
  "rating": 3.3,
  "files": []
}
```

Les champs non reconnus sont conservés dans `challenge_metadata`.

## Workspace d'un challenge

Chaque challenge est exécuté dans un dossier isolé:

```text
.challenges/<slug>-<hash>/
```

Ce dossier contient:

- `challenge.json`: manifeste normalisé
- `artifacts/`: copie des fichiers fournis
- `.runs/`: sorties et traces des workers

Exemple:

```text
.challenges/evaluative-84c696b5/
  challenge.json
  artifacts/
  .runs/
```

## Workers

### `mock`

Backend de test sans consommation de quota. Utile pour valider le graphe et les transitions d'état.

### `codex`

Le worker `codex` utilise `codex exec` avec:

- `--json` pour les événements détaillés
- `--output-schema` pour forcer un JSON final
- `-o` pour écrire le dernier message dans un fichier
- `-C` pour exécuter dans le workspace du challenge

Chaque tentative écrit:

- le prompt dans `.runs/codex/attempt-XX-prompt.txt`
- le schéma JSON dans `.runs/codex/attempt-XX-schema.json`
- le flux d'événements dans `.runs/codex/attempt-XX-events.jsonl`

Si `CODEX_STREAM_EVENTS=1`, les événements `command_execution` sont affichés en temps réel:

```text
[codex] start: /bin/zsh -lc ls
[codex] done (0): /bin/zsh -lc ls
```

### `claude`

Le worker `claude` utilise `claude -p` avec schéma JSON structuré. Il est branché, mais le plus gros du travail récent a été fait sur `codex`.

## Variables d'environnement utiles

- `CODEX_MODEL`
- `CODEX_SANDBOX`
- `CODEX_APPROVAL_POLICY`
- `CODEX_EXTRA_ARGS`
- `CODEX_TIMEOUT_SECONDS`
- `CODEX_STREAM_EVENTS`
- `CLAUDE_MODEL`
- `CLAUDE_PERMISSION_MODE`
- `CLAUDE_EXTRA_ARGS`
- `CLAUDE_TIMEOUT_SECONDS`

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Limites actuelles

- pas encore de parallélisme multi-challenges
- pas encore de planificateur global de CTF entier
- pas encore de persistance durable autre que le workspace local
- pas encore d'UI live dédiée au-dessus du streaming stderr
- pas encore d'intégration Discord
- pas encore d'exploitation automatique des `references/` des skills

## Roadmap courte

- orchestration de plusieurs challenges en parallèle
- meilleure observabilité live
- workers plus stricts sur la preuve d'exploitation
- support plus riche des cibles réseau et des artefacts
- stratégies de fallback entre workers spécialisés
