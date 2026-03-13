---
name: ctf-web-solver
description: Résolution agressive de challenges CTF Web: cartographie applicative ciblée, quick wins à faible coût, logique métier, injections et PoC scriptés avec garde-fous contre le fuzzing large et le bruit inutile.
---

# CTF Web Solver

## Workflow
1. Cartographier rapidement: routes visibles, rôles, cookies, JWT, JS, formulaires, API, uploads, stockage côté client.
2. Comprendre le trust model avant de fuzz: qui décide, qui signe, qui contrôle l'accès, où la donnée traverse une frontière.
3. Lister les quick wins probables, puis choisir 2 ou 3 pistes maximum.
4. Reproduire chaque hypothèse avec un PoC scripté court.
5. Si la cible distante est instanciée, privilégier l'interaction directe avec `curl`, `httpie` ou `requests`.
6. Réduire la chaîne d'exploitation à la requête utile et extraire le flag proprement.

## Quick Wins
- IDOR, auth bypass, trust côté client, rôle implicite, debug routes, fichiers de backup
- path traversal, file read, upload, template injection, deserialization légère
- JWT/session mal validé, signature absente, confusion algorithme, cookies prévisibles
- SSRF simple, open redirect utile, CSRF logique, race triviale
- injection SQL/NoSQL/SSTI/XPath quand l'entrée et la sink sont proches

## High-Value Pivots
- lire le HTML, le JS, les réponses d'erreur et les metadata avant de lancer de la découverte
- si le frontend révèle des endpoints, les appeler directement sans passer par l'UI
- pour les APIs, construire rapidement une collection de requêtes minimales reproductibles
- utiliser `ffuf` ou équivalent seulement si une convention de nommage ou un hint la justifie

## Resource Traps
- pas de dirbusting large "pour voir"
- pas de matrices géantes de payloads ni de fuzzing multi-thread agressif
- pas de scans infra hors périmètre applicatif du challenge
- si une piste logique échoue proprement, pivoter au lieu de multiplier les variantes mineures

## Tool Bias
- `curl`, `httpie`, `jq`, `requests`
- Burp ou proxy optionnel, mais le solve doit rester reproductible en CLI
- `ffuf` avec wordlists courtes et scope borné si nécessaire

## Minimum Output
- vulnérabilité racine
- requête ou PoC fiable
- chaîne d'exploitation
- flag
