# Production Cutover

## Pre-cutover checklist

- [ ] Backup SQLite DB: `cp /path/to/douini.db /path/to/douini.db.bak`
- [ ] Dry-run migration: `python scripts/migrate_sqlite_to_pg.py --sqlite-path /path/to/douini.db --postgres-url "$DATABASE_URL" --dry-run`
- [ ] Verify row counts match expectations
- [ ] Backup PPE PostgreSQL (if any data): `infra/scripts/backup.sh`
- [ ] Notify users of maintenance window

## Cutover steps

1. **Stop old app** (douini-run NiceGUI)
2. **Run migration**:
   ```sh
   python scripts/migrate_sqlite_to_pg.py \
     --sqlite-path /path/to/douini.db \
     --postgres-url "$DATABASE_URL"
   ```
3. **Run Alembic** (ensure schema current):
   ```sh
   cd backend && alembic upgrade head
   ```
4. **Deploy new stack**:
   ```sh
   infra/scripts/deploy.sh
   ```
5. **Smoke tests**:
   - `curl https://<domain>/api/v1/health` → `{"status":"ok"}`
   - Login with existing user
   - View plan, sessions, profile
   - Garmin status check

6. **Update DNS** to point to new server

## Rollback

1. DNS back to old server
2. Stop new stack: `docker compose -f infra/compose.yml down`
3. Start old app
4. Investigate migration issues

## Post-cutover monitoring

- Watch logs: `docker compose -f infra/compose.yml logs -f`
- Check error rates for 24h
- Verify all users can access plans
- Confirm Garmin sync works for connected users
