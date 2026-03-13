---
name: ctf-jail-solver
description: Résolution agressive de challenges CTF Jail/Sandbox: classification de contraintes, reproduction locale, payloads courts, récupération de primitives utiles et échappement borné sans fuzzing aveugle.
---

# CTF Jail Solver

## Workflow
1. Identifier le type de sandbox: pyjail, shell restreint, filtre AST, blacklist, namespace, seccomp, template jail.
2. Reproduire localement la contrainte dès que possible.
3. Chercher la primitive gagnante: récupération de builtins, lecture fichier, import, exécution indirecte, syscall autorisé, escape de template.
4. Garder les payloads courts, déterministes et compatibles avec le format d'entrée.
5. Si une primitive est obtenue, enchaîner immédiatement vers lecture du flag ou exécution minimale.

## Quick Wins
- récupération d'objets via MRO, `__subclasses__`, `globals`, closures, exceptions, format strings
- imports indirects, accès à `open`, `os`, `sys`, loaders ou modules déjà chargés
- bypass de blacklist par concaténation, encodage, aliasing, objets existants
- shell jail: variables d'environnement, expansion, redirections, interprètes accessibles
- seccomp ou sandbox syscall: lire la politique effective et exploiter les syscalls encore permis

## High-Value Pivots
- écrire un harness local qui teste les payloads et capture les erreurs
- classer la contrainte avant de générer des payloads
- si un filtre est syntaxique, raisonner sur le parseur; s'il est runtime, raisonner sur l'objet graph ou les syscalls
- réduire chaque tentative à une primitive claire: obtenir un nom, un handle, un fd, un import, une lecture

## Resource Traps
- pas de listes massives de payloads copiées sans adaptation
- pas de fuzzing aveugle des caractères, tokens ou AST
- pas de boucles distantes agressives si la jail tourne sur une instance partagée
- si une idée nécessite trop de gadgets, c'est souvent la mauvaise primitive

## Tool Bias
- Python local pour harness et payload generation
- `strace`, `seccomp-tools`, `strings`, `rg` selon le contexte
- `pwntools` si le challenge est interactif

## Minimum Output
- contrainte identifiée
- primitive gagnante
- payload ou script final
- flag
