---
name: ctf-writeup-writer
description: Rédaction de writeups CTF clairs, courts et reproductibles après résolution: explication de la démarche, commandes/scripts utiles, ton sec avec une légère touche d'humour et de mépris pour le design cassé.
---

# CTF Writeup Writer

## Usage
À utiliser après résolution d'un challenge pour produire un `writeup.md` lisible par un humain technique sans devoir relire tout l'historique brut.

## Workflow
1. Lire le challenge, le flag, le résumé final, les dernières tentatives utiles, les commandes et les scripts inline.
2. Reconstruire uniquement la démarche qui a réellement servi à solve.
3. Expliquer d'abord l'idée d'attaque simplement, puis l'exploitation concrète.
4. Inclure les commandes exactes et les scripts minimaux nécessaires à la reproduction.
5. Supprimer le bruit: fausses pistes, logs inutiles, répétitions et détails sans impact.

## Style
- Court, clair, technique, facile à suivre.
- Privilégier la prose nette aux listes interminables.
- Une légère touche d'humour sec et de mépris est autorisée, mais elle doit viser le design cassé, la primitive mal utilisée ou l'erreur évidente.
- Ne jamais viser le lecteur.
- Ne pas transformer le writeup en sketch.

## Structure attendue
- `# Writeup`
- `## Challenge`
- `## Approach`
- `## Exploit`
- `## Solve`
- `## Scripts` si un script court est central
- `## Flag`

## Contraintes
- Ne rien inventer.
- Ne garder que des étapes appuyées par l'historique, les commandes, les scripts et le résumé final.
- Dans `## Solve`, inclure des commandes reproductibles.
- Si aucun script n'est nécessaire, omettre `## Scripts`.
- Si aucune commande shell n'a servi, le dire explicitement.
