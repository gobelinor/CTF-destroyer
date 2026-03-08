name: ctf-stego-solver
description: Résolution de challenges CTF Stéganographie (image/audio/video/fichiers): détection de couches cachées, extraction de payload, décodage et récupération de flag.
---

# CTF Stego Solver

## Workflow
1. Identifier le média et signatures anormales.
2. Exécuter batterie standard (metadata, strings, LSB, binwalk, spectrogramme).
3. Tester mots de passe probables/contextuels.
4. Extraire payload puis décoder (compression/chiffrement/encodage).

## Outils
- `exiftool`, `binwalk`, `zsteg`, `steghide`
- `strings`, `xxd`, `file`
- outils audio/spectrogramme selon cas

## Blocage
Si aucune extraction n’aboutit après la batterie standard, documenter les signatures, métadonnées et outils déjà essayés avant d’élargir les hypothèses.

## Sortie minimale
- technique détectée
- commande d’extraction
- décodage final
- flag
