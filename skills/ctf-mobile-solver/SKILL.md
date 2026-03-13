---
name: ctf-mobile-solver
description: Résolution agressive de challenges CTF Mobile: triage APK/IPA, analyse statique terminal-first, endpoints et secrets, stockage local, composants exportés, instrumentation minimale et solve script reproductible.
---

# CTF Mobile Solver

## Workflow
1. Identifier l'artefact: APK, AAB, IPA, Mach-O, dump filesystem, proxy trace.
2. Faire une passe statique immédiate: manifest, permissions, composants, endpoints, strings, ressources, librairies natives.
3. Chercher les quick wins locaux avant toute instrumentation.
4. Si un backend distant existe, appeler directement ses endpoints avec un script court.
5. Passer en dynamique seulement si la statique confirme une surface utile: stockage, intents, pinning, logique runtime.
6. Réduire le solve à une extraction locale, un patch léger ou une séquence de requêtes reproductible.

## Quick Wins
- secrets, flags, URLs, tokens, mots de passe ou clés hardcodés
- composants exportés, deeplinks, intent filters, providers ou activities mal protégés
- `shared_prefs`, bases SQLite, fichiers internes, logs, cache, assets
- vérifications root/debug/pinning triviales à contourner
- endpoints mobiles non exposés dans l'UI mais présents dans le code ou les ressources

## High-Value Pivots
- Android: `aapt dump badging`, `apktool d`, `jadx`, `strings`, `rg`
- si l'app parle à une API, reconstruire l'appel en CLI avant toute émulation lourde
- utiliser `adb logcat`, `adb shell run-as`, `adb pull` ou Frida de façon ciblée seulement si la surface est confirmée
- iOS: `strings`, `plutil`, inspection du bundle, des entitlements et des plist si un IPA est fourni

## Resource Traps
- pas d'instrumentation invasive sans hypothèse claire
- pas de batterie Frida large ni de hook shotgun
- pas d'émulation complète si une analyse locale suffit
- si le remote est instable, revenir à la statique et à la reproduction de protocole

## Tool Bias
- `aapt`, `apktool`, `jadx`, `strings`, `rg`, `sqlite3`
- `adb`, `frida`, `objection` seulement quand la statique ne suffit plus
- `curl`, `requests` pour les backends

## Minimum Output
- surface mobile utile
- artefact ou flux exploité
- commande ou script final
- flag
