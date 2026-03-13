---
name: ctf-misc-solver
description: Résolution agressive de challenges CTF Misc: triage de formats hybrides, protocoles custom, automatisation minimale, réduction du problème à un pipeline scriptable et pivot rapide vers le flag.
---

# CTF Misc Solver

## Workflow
1. Décrire le contrat entrée/sortie exact du challenge.
2. Réduire le problème à un parser, un automate, une transformation ou un protocole minimal.
3. Tester les quick wins évidents sur l'encodage, le transport, les bornes et l'état.
4. Écrire un script court qui journalise les étapes utiles et stabilise les essais.
5. Si une sous-discipline devient dominante, pivoter explicitement vers cette lecture sans perdre le solve script.

## Quick Wins
- encodages empilés, compression, sérialisation, JSON/binary framing
- protocoles texte ou menu interactif avec états simples
- erreurs d'index, limites, timestamps, checksums, seeds, génération déterministe
- puzzles qui se réduisent à une recherche bornée ou à un automate fini

## High-Value Pivots
- parser d'abord, optimiser ensuite
- normaliser les entrées et sorties avant d'inférer une logique cachée
- utiliser des transcripts courts pour comprendre le protocole au lieu de tester à l'aveugle
- conserver un mode local ou mock pour itérer rapidement

## Resource Traps
- pas de fuzzing massif sans comprendre le format
- pas de brute force de paramètres multiples sans réduction
- pas d'automate géant ou de simulation lourde si un invariant plus simple existe
- si le problème reste flou après 3 approches, re-spécifier l'I/O et repartir du plus petit cas

## Tool Bias
- Python standard library, `pwntools`, `requests`
- `jq`, `awk`, `sed`, `xxd`, `nc`

## Minimum Output
- structure du problème
- pipeline ou script final
- hypothèse gagnante
- flag
