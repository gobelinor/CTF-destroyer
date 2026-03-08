name: ctf-forensics-solver
description: Résolution de challenges CTF Forensics (disk, memory, pcap, logs, metadata): timeline, extraction d’artefacts, corrélation d’événements et preuve de compromission jusqu’au flag.
---

# CTF Forensics Solver

## Workflow
1. Identifier type d’évidence (image disque, RAM, pcap, logs).
2. Préserver hash/chaîne de traitement.
3. Extraire artefacts clés (fichiers cachés, creds, IoC, exfil).
4. Construire timeline et hypothèse d’attaque.
5. Vérifier indicateur menant au flag.

## Outils
- `binwalk`, `foremost`, `exiftool`
- volatility/rekall (RAM)
- wireshark/tshark (pcap)
- grep/awk/jq pour logs

## Blocage
Si le format reste ambigu ou la timeline incohérente après plusieurs extractions, figer les résultats obtenus et repartir de l’artefact pivot le plus prometteur.

## Sortie minimale
- artefact pivot
- timeline courte
- méthode d’extraction
- flag
