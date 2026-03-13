---
name: ctf-crypto-solver
description: Résolution agressive de challenges CTF Crypto: identification rapide de primitive, réduction mathématique, quick wins classiques, solve scripts Python/Sage et garde-fous contre le brute force coûteux.
---

# CTF Crypto Solver

## Workflow
1. Identifier précisément la primitive, les paramètres, les encodages, l'oracle éventuel et la donnée à récupérer.
2. Réduire le problème avant de coder: relation algébrique, fuite, invariant, petit exemple, borne sur l'espace de recherche.
3. Tester d'abord les quick wins à coût faible.
4. Choisir 2 pistes sérieuses maximum: erreur d'implémentation, faiblesse mathématique, ou faiblesse protocolaire.
5. Écrire un `solve.py` ou `solve.sage` dès qu'une hypothèse tient.
6. Valider le flag localement et conserver la chaîne de calcul minimale.

## Quick Wins
- conversions hex/base64/int/bytes et endianness
- XOR simple, répété, Vigenère, substitution, OTP réutilisé
- RSA: petit `e`, fermat, wiener, common modulus, CRT fault, oracle naïf
- modes AES mal employés: ECB, IV/nonce réutilisé, CTR/GCM misuse, padding oracle
- hash et MAC: length extension, confusion hash/MAC, comparaison tronquée
- RNG: seed faible, LCG, MT19937, nonce prévisible

## High-Value Pivots
- écrire des checks qui invalident une famille d'attaques avant de lancer un solveur
- exploiter les tailles, répétitions, collisions, sorties partielles, erreurs de parsing
- extraire une relation sur les inconnues avant de lancer Z3, OR-Tools ou une lattice
- si une oracle distante existe, construire un client scripté court et vérifier la stabilité du protocole

## Resource Traps
- pas de bruteforce non borné sur clés, seeds, nonces ou messages
- pas de solveur lourd sans réduction préalable ni estimation de coût
- une seule tâche coûteuse à la fois: lattice, SAT/SMT, DP, MITM, gros dictionnaire
- si la mémoire ou le temps croît vite sur un petit cas, stopper et réduire mieux
- ne pas relancer plus large une piste déjà en timeout sans nouveau pruning convaincant

## Tool Bias
- Python avec `pycryptodome`, `hashlib`, `gmpy2`, `sympy`
- SageMath seulement quand la réduction mathématique le justifie
- `pwntools` ou `requests` pour les oracles distants

## Minimum Output
- primitive et hypothèse gagnante
- propriété exploitée ou erreur d'implémentation
- script final reproductible
- flag
