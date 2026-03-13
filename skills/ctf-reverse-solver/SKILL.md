---
name: ctf-reverse-solver
description: Résolution agressive de challenges CTF Reverse: triage statique, focalisation sur la routine critique, instrumentation minimale, reconstruction d'algorithme, keygen ou patch reproductible.
---

# CTF Reverse Solver

## Workflow
1. Identifier le format: ELF, PE, Mach-O, script, bytecode, firmware, APK, wasm.
2. Faire une passe statique légère: imports, strings, symboles, sections, constantes, appels suspects.
3. Isoler la zone critique: routine de check, déchiffrement, VM simple, comparateur, dérivation de clé.
4. Instrumenter seulement ce qui manque: breakpoint, trace ciblée, patch léger, emulateur local.
5. Réduire la logique à un script de solve ou un keygen.
6. Garder uniquement la chaîne utile vers le flag.

## Quick Wins
- flag en clair, segments data utiles, comparaisons naïves, transformations XOR/ROL/ADD/SUB
- lookup tables, CRC/checksum, obfuscation légère, bytecode ou VM minimaliste
- checks anti-debug simples qui se patchent ou se contournent sans bruit

## High-Value Pivots
- privilégier `file`, `strings`, `objdump`, `readelf`, `rizin` ou équivalent avant une grosse décompilation
- quand une fonction ressort, reconstruire ses entrées/sorties avant de parcourir tout le binaire
- si le remote ne fait qu'exécuter la même logique, résoudre localement d'abord
- si un solveur symbolique est utile, l'appliquer à une fonction réduite, pas au programme entier

## Resource Traps
- pas de symbolic execution globale sans réduction sévère
- pas d'analyse profonde de toutes les fonctions "au cas où"
- pas de fuzzing du binaire si une routine de validation est identifiable
- si la fonction critique reste floue, réduire encore la surface d'analyse

## Tool Bias
- `file`, `strings`, `objdump`, `readelf`, `nm`
- `rizin`/`radare2`, Ghidra headless si disponible
- `gdb`, `lldb`, `angr`, `z3` seulement sur une cible réduite

## Minimum Output
- routine critique
- logique reconstruite
- solve script, patch ou keygen
- flag
