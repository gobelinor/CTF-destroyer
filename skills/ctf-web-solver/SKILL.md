name: ctf-web-solver
description: Résolution de challenges CTF Web (auth, injection, SSRF, deserialization, template injection, logic flaws): recon applicatif, reproduction, exploitation contrôlée et exfiltration de flag.
---

# CTF Web Solver

## Workflow
1. Cartographier surface: routes, paramètres, rôles, flux auth.
2. Tester vuln classiques: SQLi, XSS, SSTI, SSRF, IDOR, upload, path traversal, race.
3. Vérifier logique métier (contournements, trust côté client, JWT/session).
4. Écrire PoC propre (requêtes scriptées) puis extraire flag.

## Outils
- Burp suite, curl/httpie
- ffuf/gobuster pour découverte
- scripts Python requests

## Blocage
Si la vulnérabilité soupçonnée ne se concrétise pas après plusieurs variantes, revenir à la cartographie des routes, des rôles et de la logique métier avant de changer de piste.

## Sortie minimale
- vuln root cause
- requête/PoC fiable
- chaîne d’exploit
- flag
