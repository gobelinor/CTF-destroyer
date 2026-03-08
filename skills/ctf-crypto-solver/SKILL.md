name: ctf-crypto-solver
description: Résolution de challenges CTF Crypto (easy à hard): identification de primitives, attaques classiques (XOR, RSA, ECC, LCG, padding, lattice), scripting Python/Sage, validation de flag.
---

# CTF Crypto Solver

## Workflow
1. Identifier la primitive: chiffrements symétriques, asymétriques, hash, PRNG, signature, protocole.
2. Classifier le niveau:
   - Easy/Medium: attaques standards directes.
   - Hard: vuln subtile, paramètres inhabituels, preuve mathématique requise.
3. Lancer 3 pistes distinctes max avant escalade:
   - erreurs d’implémentation,
   - faiblesse mathématique,
   - faiblesse protocolaire.
4. Produire un solve script reproductible (`solve.py`/`solve.sage`).
5. Vérifier le flag avec regex locale.

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
- Script final
- Explication 5-10 lignes
- Flag
