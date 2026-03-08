name: ctf-osint-solver
description: Résolution de challenges CTF OSINT: pivoting sur identités, géolocalisation, corrélation de sources ouvertes, validation d’indices et production de preuve menant au flag.
---

# CTF OSINT Solver

## Workflow
1. Extraire tous les indicateurs initiaux (usernames, domaines, images, dates).
2. Pivot contrôlé: mêmes handles, fuites metadata, archives web.
3. Corréler au moins 2 sources indépendantes par hypothèse.
4. Vérifier format flag demandé.

## Outils
- recherche avancée opérateurs
- exiftool, reverse image, maps
- wayback + archives publiques

## Blocage
Si le pivot principal est épuisé, lister les identifiants, dates et sources déjà vérifiés avant d’ouvrir une nouvelle branche de corrélation.

## Sortie minimale
- chaîne de pivots
- preuves croisées
- réponse finale/flag
