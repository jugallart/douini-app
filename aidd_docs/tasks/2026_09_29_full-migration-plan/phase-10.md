---
status: pending
---

# Instruction: CI/CD (GitHub Actions)

## Architecture projection

> Tree of the final files. ✅ create · ✏️ modify · ❌ delete

```txt
.github/
  workflows/
    ci.yml                            ✅ create  — tests + typecheck + lint sur chaque push et PR
    deploy.yml                        ✅ create  — build + push image + deploy sur merge main
  dependabot.yml                      ✅ create  — mises à jour de sécurité automatisées
```

## User Journey

```mermaid
flowchart TD
  A[Push sur une branche feature] --> B[ci.yml déclenché]
  B --> C[pytest 470 tests]
  C --> D[TypeScript typecheck web + mobile + shared]
  D --> E{Tout vert ?}
  E -- Non --> F[PR bloquée]
  E -- Oui --> G[PR mergeable]
  G --> H[Merge vers main]
  H --> I[deploy.yml déclenché]
  I --> J[Build + push images Docker avec digest SHA]
  J --> K[SSH vers VPS, lancer deploy.sh avec le digest]
  K --> L[Health check passe]
  L --> M[Déploiement terminé]
```

## Test Scope

```mermaid
---
title: Test scope
---
journey
  section CI
    Push sur une branche => ci.yml s'exécute en moins de 10 min: 5: github
    Test échouant => workflow échoue PR bloquée: 1: github
    Erreur TypeScript => workflow échoue: 1: github
    Tous les checks passent => workflow vert: 5: github
  section Deploy
    Merge vers main => deploy.yml déclenché: 5: github
    Image poussée avec tag SHA => digest immuable: 5: github
    Health check VPS passe après deploy => workflow vert: 5: github
    Échec deploy => workflow échoue image précédente toujours en cours: 1: github
  section Dependabot
    PRs de sécurité apparaissent dans la semaine: 5: github
```

## Tasks to do

### `1)` Créer .github/workflows/ci.yml

> Mettre en place le workflow CI exécutant tests backend et typecheck frontend sur chaque push et PR.

1. Trigger : on: [push, pull_request].
2. Job test-backend :
   - runs-on: ubuntu-latest
   - Service postgres:16-alpine avec health check pg_isready
   - Steps : actions/checkout@v4, actions/setup-python@v5 avec Python 3.11, pip install -e backend/[dev], pytest backend/tests/ -q --tb=short
   - Env : DATABASE_URL=postgresql+psycopg://douini:douini@localhost:5432/douini, SECRET_KEY=test-secret-key-32-chars-minimum-ok, ENVIRONMENT=dev, DOUINI_ENCRYPTION_KEY= (généré via python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
3. Job typecheck :
   - runs-on: ubuntu-latest
   - Steps : actions/checkout@v4, actions/setup-node@v4 avec Node 22, npm ci, npm run typecheck --workspaces --if-present
4. Toutes les versions d'actions sont pinnées (ex. actions/checkout@v4, pas @main).

### `2)` Créer .github/workflows/deploy.yml

> Mettre en place le workflow de déploiement déclenché sur merge vers main avec build, push d'images et SSH vers le VPS.

1. Trigger : on: push: branches: [main].
2. Conditionné par le succès de ci.yml (utiliser workflow_run ou needs si workflows combinés).
3. Job build-and-push :
   - Login sur ghcr.io avec GITHUB_TOKEN
   - Build infra/Dockerfile.backend + infra/Dockerfile.web
   - Tags : ghcr.io/${{ github.repository_owner }}/douini-backend:${{ github.sha }} et ...-web:${{ github.sha }}
   - Push et récupérer le digest de l'image
4. Job deploy (dépend de build-and-push) :
   - SSH vers le VPS via appleboy/ssh-action@v1 (version pinnée)
   - Exécuter deploy.sh ${{ github.sha }}
   - Vérifier le health check
5. Secrets GitHub requis : VPS_HOST, VPS_USER, VPS_SSH_KEY.
6. Pas de déploiement PROD automatique — PROD nécessite un workflow_dispatch manuel ou un trigger sur tag v*.

### `3)` Créer .github/dependabot.yml

> Configurer Dependabot pour les mises à jour de sécurité hebdomadaires sur pip, npm et GitHub Actions.

1. Créer le fichier .github/dependabot.yml avec la configuration suivante :
   ```yaml
   version: 2
   updates:
     - package-ecosystem: pip
       directory: /backend
       schedule:
         interval: weekly
       open-pull-requests-limit: 3

     - package-ecosystem: npm
       directory: /
       schedule:
         interval: weekly
       open-pull-requests-limit: 3

     - package-ecosystem: github-actions
       directory: /
       schedule:
         interval: weekly
       open-pull-requests-limit: 3
   ```

### `4)` Protection de branche (via UI GitHub, documentée)

> Sécuriser la branche main avec des checks de statut obligatoires et empêcher le force push.

1. Exiger le check de statut ci.yml sur main.
2. Interdire le force push sur main.
3. Pour un dev solo : documenter la décision de bypass de la revue obligatoire.

## Test acceptance criteria

| Task | Acceptance criteria              |
| ---- | -------------------------------- |
| 1    | CI s'exécute sur push ; 470 tests passent en CI ; typecheck TypeScript passe |
| 2    | Push vers main déclenche le déploiement ; digest immuable utilisé ; health check vérifié dans le workflow |
| 3    | PRs Dependabot apparaissent pour les deps de sécurité obsolètes dans la semaine |
| 4    | Protection de branche documentée ; check CI requis non contournable |
