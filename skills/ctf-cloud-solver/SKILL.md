---
name: ctf-cloud-solver
description: Résolution agressive de challenges CTF Cloud: identité d'abord, scope minimal, secrets et config, objets exposés, metadata, IAM, kube/containers et garde-fous contre l'énumération large d'infrastructure.
---

# CTF Cloud Solver

## Workflow
1. Identifier la plateforme, les credentials disponibles, le contexte d'exécution et le périmètre réel du challenge.
2. Vérifier l'identité courante avant toute énumération.
3. Extraire les artefacts locaux d'abord: `.env`, kubeconfig, Terraform, Compose, manifests, CI, service accounts, images.
4. Énumérer uniquement les ressources liées aux indices du challenge.
5. Exploiter la relation de confiance utile: bucket public, rôle mal lié, secret exposé, metadata accessible, RBAC permissif.
6. Réduire la résolution à quelques commandes CLI ou un script reproductible.

## Quick Wins
- `aws sts get-caller-identity`, `gcloud auth list`, `az account show`, `kubectl config current-context`
- buckets/blobs publics, variables d'environnement, secrets dans images ou pipelines
- IAM trop large, service account réutilisable, kube token, dashboard ou API interne exposée
- metadata service accessible depuis un container ou une app du challenge
- registry ou artefact CI contenant creds, clés, manifests ou historiques utiles

## High-Value Pivots
- identity-first: savoir qui on est avant de lister
- kube/containers: vérifier namespace, service account, mounted secrets, rights effectifs
- cloud storage: cibler les noms, régions ou préfixes indiqués par l'énoncé
- si une app web ou mobile sert de pivot cloud, exploiter d'abord l'app puis suivre la trust relationship

## Guardrails
- ne jamais scanner un compte, un tenant ou un cluster entier sans indice explicite
- ne pas perturber de workloads ni provoquer de surcharge
- rester dans les ressources du challenge; pas de pentest générique du fournisseur cloud

## Resource Traps
- pas de récursion large sur toutes les régions, tous les projets, tous les namespaces
- pas de `kubectl get all -A` ou équivalent sans justification forte
- pas d'essais massifs de rôles ou secrets
- si une commande renvoie trop de bruit, réduire le scope ou revenir aux artefacts locaux

## Tool Bias
- `aws`, `gcloud`, `az`, `kubectl`, `docker`
- `jq`, `yq`, `rg`, `env`, `strings`

## Minimum Output
- identité et périmètre utile
- ressource ou trust abuse retenu
- commandes finales
- flag
