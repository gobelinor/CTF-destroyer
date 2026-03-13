---
name: ctf-pwn-solver
description: Résolution agressive de challenges CTF Pwn: triage des protections, identification de primitive mémoire, leak, contrôle de flux, exploit pwntools stable et garde-fous contre les approches bruyantes ou aléatoires.
---

# CTF Pwn Solver

## Workflow
1. Triage immédiat: arch, libc, NX, PIE, RELRO, canary, binaire dynamique ou statique.
2. Comprendre le protocole I/O avant de chercher des gadgets.
3. Identifier la primitive réelle: read/write, overflow, format string, UAF, double free, race locale, OOB.
4. Obtenir un leak fiable ou une primitive de réécriture simple avant de complexifier.
5. Stabiliser localement avec `pwntools`, puis reproduire sur la cible distante.
6. Garder l'exploit court, paramétrable et orienté flag.

## Quick Wins
- ret2win, shellcode obvious, format string triviale, GOT overwrite sous protections faibles
- index signé/non signé, taille contrôlée, lecture arbitraire, off-by-one, menu mal borné
- mauvaises hypothèses sur `scanf`, `printf`, `gets`, `read`, `strcpy`, chunks heap simples

## High-Value Pivots
- `file`, `checksec`, `ldd`, `strings`, `objdump` avant GDB profond
- un harness local qui reproduit exactement les échanges
- fuites de stack, libc, heap ou bss avant la chaîne finale
- si la corruption heap est complexe, revenir au modèle des chunks et aux invariants allocator

## Resource Traps
- pas de bruteforce d'adresses si l'entropie n'est pas faible et bornée
- pas de spray de gadgets ou de chaînes ROP énormes sans primitive stable
- pas de boucles distantes agressives qui peuvent dégrader l'instance du CTF
- si l'exploit est flaky, réduire: leak, synchronisation, tailles, state machine

## Tool Bias
- `checksec`, `objdump`, `readelf`, `strings`
- `pwntools`, `gdb`, `pwndbg`, `ROPgadget`
- `one_gadget` ou `libc-database` seulement si la chaîne le justifie

## Minimum Output
- primitive retenue
- leak ou invariant critique
- exploit final
- flag
