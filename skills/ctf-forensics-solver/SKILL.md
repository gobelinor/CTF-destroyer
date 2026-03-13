---
name: ctf-forensics-solver
description: Résolution agressive de challenges CTF Forensics: classification d'évidence, extraction ciblée, timeline courte, corrélation d'artefacts et pivot rapide vers la preuve utile ou le flag.
---

# CTF Forensics Solver

## Workflow
1. Classer l'évidence: image disque, mémoire, pcap, logs, document, dump navigateur, archive.
2. Travailler sur copies ou sorties dérivées quand la mutation du fichier est possible.
3. Faire un triage léger: `file`, tailles, hashes, strings, métadonnées, structure interne.
4. Choisir l'artefact pivot le plus prometteur, puis construire un pipeline d'extraction minimal.
5. Corréler les timestamps, chemins, identifiants, sessions ou flux réseau jusqu'au flag.
6. Garder une timeline courte et seulement les indicateurs réellement utiles.

## Quick Wins
- archives ou couches imbriquées, fichiers supprimés, metadata parlantes
- historique shell, browser, clipboard, documents office, macros, artefacts d'upload
- pcaps avec HTTP, DNS, FTP, SMTP, TLS non chiffré ou objets exportables
- mémoire avec processus suspects, chaînes en clair, creds, sockets, commandes
- logs avec tokens, traces d'accès, chemins de fichiers, événements anormaux

## High-Value Pivots
- pour disque: monter ou parcourir l'arborescence avant de lancer une batterie complète de carvers
- pour RAM: lister processus, réseau et fichiers ouverts avant les plugins lourds
- pour pcap: filtrer par protocole, hôte, objet transféré, session ou erreur
- pour logs: isoler la fenêtre temporelle la plus dense et réduire le bruit avec `jq`, `awk`, `rg`

## Resource Traps
- ne pas lancer tous les extracteurs lourds en parallèle
- ne pas reconstruire une timeline globale exhaustive si une plage courte suffit
- ne pas carver tout un dump sans indice sur le type d'objet recherché
- si un outil produit énormément de bruit, réduire d'abord le scope ou pivoter

## Tool Bias
- `file`, `strings`, `xxd`, `jq`, `rg`
- `binwalk`, `foremost`, `exiftool`
- `tshark`, `tcpflow`, `capinfos`
- `volatility` ou équivalent seulement après triage mémoire

## Minimum Output
- artefact pivot
- méthode d'extraction
- preuve courte ou timeline courte
- flag
