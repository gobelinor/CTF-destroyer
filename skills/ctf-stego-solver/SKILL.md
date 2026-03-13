---
name: ctf-stego-solver
description: Résolution agressive de challenges CTF Stéganographie: inspection de médias, détection de couches cachées, extraction ciblée, décodage et garde-fous contre les batteries d'outils trop larges ou les attaques de mot de passe inutiles.
---

# CTF Stego Solver

## Workflow
1. Identifier le média exact et vérifier signature, dimensions, durée, codec, conteneur et anomalie de taille.
2. Commencer par la couche la plus visible: metadata, appended data, strings, archives imbriquées, canaux couleur ou bitplanes.
3. Tester ensuite les techniques probables liées au média: LSB image, spectrogramme audio, frames vidéo, fichiers cachés.
4. Si un mot de passe semble plausible, le dériver du contexte du challenge avant tout dictionnaire.
5. Décoder, décompresser ou déchiffrer le payload seulement après extraction fiable.

## Quick Wins
- `exiftool`, `file`, `xxd`, `strings`, `binwalk`
- pixels anormaux, alpha, palette, ordre des canaux, appended ZIP/TAR
- audio avec message en spectre ou symboles simples
- texte ou archives dissimulés via stégo classique `zsteg`, `steghide`

## High-Value Pivots
- comparer original apparent et structure réelle du fichier
- extraire une couche à la fois au lieu de lancer tous les outils puis tout mélanger
- si un payload sort, l'analyser comme un nouveau challenge à part entière
- utiliser des scripts courts pour tester une hypothèse de canal ou de permutation

## Resource Traps
- pas de password cracking large sans mot de passe contextuel crédible
- pas de batterie exhaustive de permutations, canaux ou bitplanes sans signal
- ne pas relancer les mêmes outils avec paramètres voisins sans hypothèse nouvelle

## Tool Bias
- `file`, `exiftool`, `binwalk`, `xxd`, `strings`
- `zsteg`, `steghide`, `sox`, scripts Python Pillow/Wave

## Minimum Output
- technique retenue
- commande ou script d'extraction
- décodage final
- flag
