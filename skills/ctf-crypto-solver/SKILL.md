name: ctf-crypto-solver
description: Résolution de challenges CTF Crypto (easy à hard): identification de primitives, attaques classiques (XOR, RSA, ECC, LCG, padding, lattice), scripting Python/Sage, validation de flag.
---

# CTF Crypto Solver

## Workflow
1. Identifier la primitive: chiffrements symétriques, asymétriques, hash, PRNG, signature, protocole.
2. Triage coût/risque avant exécution:
   - repérer brute force, DP volumineuse, MITM, MILP/CP-SAT/SMT, lattice, recherche sur intervalle large;
   - lire d’abord les scripts, logs et handoff déjà présents avant de relancer un solveur lourd;
   - estimer les dimensions dangereuses: taille d’état, nombre de moduli, nombre de candidats, largeur de fenêtre, parallélisme solveur.
3. Classifier le niveau:
   - Easy/Medium: attaques standards directes.
   - Hard: vuln subtile, paramètres inhabituels, preuve mathématique requise.
4. Lancer 3 pistes distinctes max avant escalade:
   - erreurs d’implémentation,
   - faiblesse mathématique,
   - faiblesse protocolaire.
5. Produire un solve script reproductible (`solve.py`/`solve.sage`) seulement après avoir réduit l’espace de recherche.
6. Vérifier le flag avec regex locale.

## Hygiène Ressources
- Toujours préférer les tests négatifs peu coûteux, bornes mathématiques, invariants et pruning avant une recherche exacte.
- Une seule tâche coûteuse à la fois. Éviter plusieurs solveurs lourds en parallèle.
- Réduire le parallélisme par défaut des solveurs exacts. Pour CP-SAT/CBC/Z3, commencer petit et n’augmenter qu’avec une raison explicite.
- Éviter les scans larges sur plusieurs longueurs, fenêtres ou sommes si le coût mémoire d’un seul cas n’est pas déjà connu.
- Si un solveur construit de gros dictionnaires d’états, bitsets, tables DP ou ensembles de candidats, mesurer sur un petit cas avant de monter en taille.
- Ne pas installer une nouvelle pile de dépendances lourdes dans le workspace sans nécessité claire. Réutiliser l’existant si possible.
- Si le coût observé croît vite avec `n`, le nombre de moduli, la largeur de fenêtre ou le nombre de candidats `k`, stopper l’escalade et pivoter vers une meilleure réduction mathématique.

## Signaux De Danger
- Recherche exacte avec états de la forme `(len, sum, sign, mask, ...)` stockés dans des `dict`.
- `candidate_ks()` ou équivalent qui renvoie beaucoup de candidats par somme.
- Solveurs OR-Tools / CBC / Z3 lancés sur de grandes plages ou avec plusieurs workers.
- Fenêtres de scan élargies "pour voir" sans borne mémoire.
- Rebuild répété du même searcher coûteux pour plusieurs cas voisins.

## Politique D'Escalade
- Si le coût mémoire ou swap n’est pas prévisible, ne pas lancer le solveur lourd en aveugle.
- Si un premier profil léger montre une croissance superlinéaire, documenter le risque et changer d’approche.
- Si une tentative précédente a déjà time-out sur une famille de recherche exacte, ne pas la répéter plus large sans nouveau pruning convaincant.
- En cas de blocage, rendre la meilleure prochaine réduction mathématique ou instrumentation ciblée au lieu d’un "scan plus grand".

## Quick checks
- Encodages: hex/base64/int bytes.
- XOR simple/répété, Vigenère, substitution.
- RSA: small e, Wiener, Fermat, CRT fault, common modulus.
- AES modes: ECB/CBC/CTR misuse, oracle padding.
- Hash: length extension, collisions pratiques, MAC misuse.
- RNG: seed recover, LCG, Mersenne Twister state recovery.

## Outils
- Python + `pycryptodome`, `gmpy2`, `pwntools`
- SageMath pour algèbre/lattice
- Factordb/pari local equivalents si nécessaire

## Blocage
Si 3 pistes distinctes échouent, documenter clairement les hypothèses déjà testées et revenir au triage de la primitive avant de changer d’approche.

## Sortie minimale
- Hypothèse validée
- Décision ressource prise (ce qui a été évité ou borné, et pourquoi)
- Script final
- Explication 5-10 lignes
- Flag
