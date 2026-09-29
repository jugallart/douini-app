# Deployment

## Dev (local)

```sh
docker compose -f infra/compose.dev.yml up -d
cd backend && uvicorn douini.api.main:app --reload
cd web && npm run dev
```

## PPE / Prod

1. Copy `.env.example` → `.env`, fill secrets:
   - `SECRET_KEY` — `openssl rand -hex 32`
   - `DOUINI_ENCRYPTION_KEY` — `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `POSTGRES_PASSWORD` — strong password
   - `CADDY_HOST` — your domain (e.g. `ppe.douini.run`)
   - `ALLOWED_ORIGINS` — `["https://ppe.douini.run"]`
   - `FRONTEND_URL` — `https://ppe.douini.run`
   - SMTP credentials

2. Deploy:
   ```sh
   infra/scripts/deploy.sh
   ```

3. Health check:
   ```sh
   curl https://<CADDY_HOST>/api/v1/health
   ```

## Backup / Restore

```sh
infra/scripts/backup.sh
infra/scripts/restore.sh backup_YYYYMMDD_HHMMSS.sql.gz
```

## Logs

```sh
docker compose -f infra/compose.yml logs -f backend
docker compose -f infra/compose.yml logs -f caddy
```
