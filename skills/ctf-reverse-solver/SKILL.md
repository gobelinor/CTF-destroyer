name: ctf-reverse-solver
description: Résolution de challenges CTF Reverse Engineering (ELF/PE/apk/scripts): triage statique, debug dynamique, patching, symbolic hints, extraction d’algorithmes et récupération de flag.
---

# CTF Reverse Solver

## Workflow
1. Identifier format binaire/script et protections.
2. Statique d’abord (strings, fonctions, graphes, constantes).
3. Dynamique ciblée (breakpoints sur compare/check routines).
4. Reconstituer logique, automatiser bypass ou keygen.
5. Produire solve script reproductible.

## Quick checks
- `file`, `checksec`, `strings`, désassemblage/decompilation
- anti-debug, obfuscation légère, VM custom simple
- transformations: xor/rol/lookup/table/substitution

## Outils
- Ghidra/IDA/Binary Ninja (selon dispo)
- gdb + peda/pwndbg
- angr/z3 si contrainte non triviale

## Blocage
Si la routine critique n’est pas comprise après un triage statique et dynamique correct, isoler la fonction cible et réduire la surface d’analyse avant de continuer.

## Sortie minimale
- fonction cible identifiée
- logique reconstruite
- solve/keygen
- flag
