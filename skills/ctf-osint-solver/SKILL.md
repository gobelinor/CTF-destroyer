---
name: ctf-osint-solver
description: Résolution agressive de challenges CTF OSINT: extraction d'indices, pivots serrés, corrélation de sources ouvertes, validation croisée et garde-fous pour rester dans un OSINT passif et rentable.
---

# CTF OSINT Solver

## Workflow
1. Extraire tous les indicateurs initiaux: noms, handles, domaines, emails, lieux, dates, images, plaques, horaires.
2. Normaliser immédiatement les variantes d'écriture, les fuseaux horaires et les formats de date.
3. Construire une chaîne de pivots courte, avec une hypothèse par branche.
4. Exiger au moins deux signaux compatibles avant de conclure.
5. Vérifier le format exact de la réponse ou du flag demandé.

## Quick Wins
- recherche exacte sur chaînes rares ou citations
- réutilisation de handle, avatar, photo, bannière, bio
- métadonnées EXIF, archives web, historique de domaines, fichiers publics exposés
- reverse image, cartographie, géolocalisation à partir d'enseignes, routes, reliefs, horaires

## High-Value Pivots
- partir des indices fournis, pas de l'internet entier
- privilégier les sources publiques déjà indexées ou facilement consultables
- noter la chaîne de preuve au fur et à mesure pour éviter les faux positifs
- croiser image + texte, date + lieu, ou identité + domaine plutôt qu'un seul axe

## Guardrails
- rester sur un OSINT passif et proportionné
- pas d'interaction intrusive, pas de harcèlement, pas de création de comptes, pas de scraping agressif
- pas de dox ni de collecte hors sujet; tout pivot doit être justifié par le challenge
- si une source tierce rate-limit ou se dégrade, ne pas insister

## Resource Traps
- ne pas ouvrir trop de branches parallèles
- ne pas surinterpréter un handle commun sans second signal
- ne pas passer trop de temps sur un pivot épuisé; documenter et changer d'axe

## Tool Bias
- recherche avancée, archives web, données publiques
- `exiftool`, `strings`, outils de reverse image selon disponibilité

## Minimum Output
- chaîne de pivots gagnante
- preuves croisées
- réponse finale ou flag
