---
name: ctf-hardware-rf-solver
description: Résolution agressive de challenges CTF Hardware/RF: triage firmware, bus, captures et signaux, extraction ciblée, décodage de protocole ou de modulation, sans partir dans des hypothèses physiques coûteuses.
---

# CTF Hardware RF Solver

## Workflow
1. Identifier le matériau réel: firmware, dump flash, log série, bus capture, fichier IQ/WAV, trame radio, schéma.
2. Commencer par l'analyse locale la plus simple: signature, structure, strings, config, système de fichiers, timing ou framing.
3. Isoler le protocole ou la couche utile avant de tester des transformations.
4. Si un signal RF est fourni, déterminer d'abord format, débit, bursts, modulation probable et symboles récurrents.
5. Écrire des scripts courts pour parser, démultiplexer ou décoder.
6. Ne retenir que la chaîne utile vers le flag, pas toute la rétro-ingénierie possible.

## Quick Wins
- firmware avec archives embarquées, configs, clés, mots de passe, pages web, scripts d'update
- UART/console, protocoles texte, commandes en clair, checksums simples
- captures RF ou audio contenant ASK/FSK, trames répétées, préambules, IDs fixes
- secrets ou flags en clair dans les dumps, EEPROM, logs ou fichiers de calibration

## High-Value Pivots
- firmware: `file`, `binwalk`, `strings`, extraction FS, recherche de credentials et endpoints
- bus/série: reconstruire les paquets et leur framing avant de spéculer sur la logique
- RF: utiliser `sox`, `rtl_433`, `multimon-ng`, scripts Python pour observer symboles, timings et répétitions
- si un protocole connu se dessine, tester ce protocole avant d'essayer toutes les modulations possibles

## Resource Traps
- pas de brute force large sur baud rates, modulations, clés ou permutations sans indice
- pas d'hypothèse de side-channel ou d'attaque physique si le challenge ne fournit que des artefacts
- pas d'extraction exhaustive de tout le firmware si une partition ou un composant ressort clairement

## Tool Bias
- `file`, `binwalk`, `strings`, `xxd`
- `sox`, `rtl_433`, `multimon-ng`, `sigrok-cli` selon les captures fournies
- scripts Python pour parser et décoder

## Minimum Output
- couche ou protocole exploité
- extraction ou décodage final
- script ou commande centrale
- flag
