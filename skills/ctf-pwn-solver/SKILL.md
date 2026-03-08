name: ctf-pwn-solver
description: Résolution de challenges CTF Pwn/Binary Exploitation: analyse protections, primitives mémoire, crafting d’exploit (BOF, format string, heap), pwntools et récupération de shell/flag.
---

# CTF Pwn Solver

## Workflow
1. Triage binaire: arch, NX/PIE/RELRO/CANARY.
2. Identifier primitive: read/write/BOF/UAF/double free/FSB.
3. Construire leak puis contrôle d’exécution.
4. Développer exploit pwntools stable local puis remote.
5. Capturer flag proprement.

## Outils
- `checksec`, gdb/pwndbg
- `pwntools`, `one_gadget`, `ROPgadget`
- libc-database (si nécessaire)

## Blocage
Si l’exploit reste instable après plusieurs itérations, revenir aux primitives de leak et au modèle mémoire avant de complexifier la chaîne d’exploitation.

## Sortie minimale
- primitive + leak
- exploit final
- preuve exécution
- flag
