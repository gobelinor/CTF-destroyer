name: ctf-misc-solver
description: Résolution de challenges CTF Misc (automatisation, encodages hybrides, protocoles custom, logique non standard): triage rapide, scripting Python/Bash, expérimentation structurée et récupération de flag.
---

# CTF Misc Solver

## Workflow
1. Triage du format d’entrée/sortie et contraintes challenge.
2. Détecter patterns: encodage multiple, protocole texte, puzzle logique, automation.
3. Écrire un script itératif (parsers robustes + logs).
4. Tester hypothèses de transformation en pipeline.

## Outils
- Python (regex, codecs, parsing)
- bash + awk/sed/jq
- netcat/pwntools pour services interactifs

## Blocage
Si la structure du problème reste ambiguë après 3 approches, résumer les entrées/sorties observées et réduire le challenge à un pipeline minimal testable.

## Sortie minimale
- structure du problème
- pipeline de transformation
- solve script
- flag
