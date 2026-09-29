# Deployment

## Local dev

```bash
docker compose -f infra/compose.dev.yml up -d    # postgres:16-alpine :5432
cd backend && alembic upgrade head
cd backend && uvicorn douini.api.main:app --reload --port 8000
npm run dev:web    # :5173
```

## Docker (PPE/prod)

```bash
docker compose -f infra/compose.yml up -d    # postgres + backend + web + caddy
```

### compose.yml services

| Service | Image | Port |
|---------|-------|------|
| postgres | postgres:16-alpine | 5432 (internal) |
| backend | Dockerfile.backend (python:3.12-slim) | 8000 (internal) |
| web | Dockerfile.web (nginx:1.27-alpine) | 80 (internal) |
| caddy | caddy:2-alpine | 80, 443 (public) |

Caddyfile: `{$CADDY_HOST}` → /api/* to backend:8000, else web:80.

### Backend Docker

Multi-stage python:3.12-slim. `pip install --require-hashes -r requirements.lock`. Non-root user. Entrypoint: `alembic upgrade head && uvicorn`.

### Web Docker

Multi-stage node:22-alpine build → nginx:1.27-alpine static. SPA fallback to index.html.

## CI/CD

`.github/workflows/ci.yml`: test-backend (postgres service + pytest), typecheck (node 22 + tsc web/mobile).

`.github/workflows/deploy.yml`: push main → build+push to ghcr.io with SHA tag → SSH to VPS → deploy.sh.

## Data migration

`scripts/migrate_sqlite_to_pg.py --sqlite-path <path> --postgres-url <url> [--dry-run]`

Order: users→profile→plans→plan_sessions→session_feedback→plan_adjustments→race_results→profile_vdot_history. ID remapping. ON CONFLICT DO NOTHING.

## Backup/restore

```bash
infra/scripts/backup.sh     # pg_dump | gzip
infra/scripts/restore.sh    # gunzip | psql (with confirmation)
```
