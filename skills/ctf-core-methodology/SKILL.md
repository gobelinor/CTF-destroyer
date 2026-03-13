---
name: ctf-core-methodology
description: Méthodologie CTF transverse, compacte et terminal-first: triage rapide, budget ressource, règles d'engagement, discipline de pivot et format de sortie pour résoudre vite sans sortir du périmètre.
---

# CTF Core Methodology

## Mission
- Résoudre vite, pas explorer large.
- Exploiter d'abord les artefacts, le texte du challenge, l'état local du workspace et la mémoire de reprise.
- Chaque commande doit tester une hypothèse ou réduire l'espace de recherche.

## Resolution Loop
1. Lire l'énoncé, les artefacts, les tentatives précédentes et les fichiers de handoff avant toute nouvelle action.
2. Identifier la surface exacte: artefact local, binaire, service distant, protocole, identité, format.
3. Lister les quick wins plausibles, puis choisir 2 hypothèses principales maximum et 1 piste de repli.
4. Lancer les checks les moins coûteux et les plus discriminants en premier.
5. Dès qu'une action se répète ou mélange plusieurs transformations, écrire un script court et reproductible.
6. Si une piste ne produit pas de signal exploitable rapidement, pivoter au lieu d'intensifier.

## Resource Policy
- Local et passif avant distant et interactif.
- Une seule opération coûteuse à la fois.
- Borner avant exécution: temps, taille, profondeur, plage, wordlist, workers, nombre d'essais.
- Préférer les tests qui invalident vite une hypothèse.
- Réutiliser scripts, logs et sorties existants avant de relancer une exploration similaire.

## Guardrails
- Rester strictement dans le périmètre du challenge.
- Ne pas pentester l'infrastructure du CTF, la plateforme, les comptes d'autres joueurs ou des services tiers hors énoncé.
- Pas de DoS, pas de flood, pas de scans larges, pas de fuzzing agressif sans indice fort.
- Pas de bruteforce non borné; si une recherche est nécessaire, justifier la borne et la réduire d'abord.
- Ne pas installer une pile lourde ou lancer plusieurs outils gourmands sans besoin explicite.

## Execution Bias
- Préférer `file`, `strings`, `jq`, `curl`, `python`, `pwntools`, `requests`, `objdump`, `tshark`, `binwalk`, `cast`, `aws`, `kubectl` ou équivalents CLI disponibles avant les workflows GUI.
- Conserver une trace minimale: hypothèse, commande utile, résultat discriminant, prochain pivot.
- Si un flag candidat apparaît, le valider contre le format attendu avant de conclure.

## Minimum Output
- Hypothèse retenue ou invalidée.
- Signal utile observé.
- Commandes ou script central.
- Prochain pas le plus rentable si non résolu.
- Flag seulement s'il est effectivement récupéré.
