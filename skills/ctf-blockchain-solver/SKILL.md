---
name: ctf-blockchain-solver
description: Résolution agressive de challenges CTF Blockchain: triage de contrats et d'état on-chain, quick wins EVM, reproduction locale avec Foundry, appels `cast`, stockage, permissions et exploitation bornée.
---

# CTF Blockchain Solver

## Workflow
1. Identifier la chaîne, le RPC, les adresses, le code source ou l'ABI, l'objectif exact du challenge et la condition de victoire.
2. Reconstruire l'état minimal: owner, rôles, soldes, storage, initializers, événements utiles.
3. Tester les quick wins à très faible coût avec des appels en lecture avant toute transaction.
4. Reproduire localement avec `anvil --fork-url` ou un test `forge` dès qu'un état précis importe.
5. Écrire un exploit déterministe, avec séquence d'appels minimale et assertions locales.
6. Soumettre seulement les transactions nécessaires à la récupération du flag ou à la condition gagnante.

## Quick Wins
- `owner` ou rôle mal initialisé, `initialize` public, access control manquant
- reentrancy, mauvaise comptabilité, sous/sur-flux legacy, précision décimale
- storage sensible lisible, slot critique écrasable, collision de storage, delegatecall abusif
- signature/permit mal lié au domaine, nonce, chaîne ou autorité
- randomness ou timestamp utilisable, oracle naïf, mauvais usage de `tx.origin`

## High-Value Pivots
- `cast call`, `cast storage`, `cast code`, `cast balance`, `cast send`
- lire événements et storage avant de fuzz les fonctions
- construire un test `forge` qui documente l'état de départ, l'exploit et l'assertion finale
- si un contrat intermédiaire est nécessaire, le garder minimal et lisible

## Resource Traps
- pas de spray de transactions ni de fuzzing on-chain large
- pas de brute force d'adresses, de seeds ou de signatures sans borne serrée
- pas de dépendance à un état non déterministe non reproduit localement
- si une piste modifie l'état de façon irréversible sans preuve suffisante, revenir au fork local

## Tool Bias
- `cast`, `forge`, `anvil`
- `solc` ou bytecode tools si nécessaire
- scripts Python/web3 seulement si Foundry ne couvre pas proprement le besoin

## Minimum Output
- état ou contrôle abusé
- séquence d'appels ou test d'exploit
- preuve de la condition gagnante
- flag
