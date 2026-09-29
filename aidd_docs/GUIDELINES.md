# AI Operating Guidelines

How this team drives AI coding assistants on this project.

## House rules

- Domain engine (`backend/douini/domain/`) is read-only vendor. Never modify it. If a domain bug is found, fix it in `douini-run` and re-copy.
- 410 domain tests must pass before any backend change ships. Run `cd backend && pytest tests/ -q`.
- Raw SQL only (psycopg3 `%s` placeholders). No ORM, no SQLAlchemy models.
- JSONB columns: psycopg3 auto-deserializes. Guard with `isinstance(x, str)` before `json.loads()`.
- bcrypt direct, not passlib. passlib 1.7.4 breaks with bcrypt 5.0.
- `@douini/shared` is the single source of truth for TypeScript types. Web and mobile import from it.
- Backend routes use `Depends(get_verified_user)` for any user-scoped endpoint.
- Cross-user access returns 404, not 403 (don't leak existence).

## Validation depth

- Domain change: full 410-test suite must pass.
- Backend route/service: smoke-test the endpoint with `python3 -c` + urllib (see session history for pattern).
- Frontend: `tsc --noEmit` clean for the affected workspace.
- Docker/CI: dry-run the workflow or `docker compose config` to validate.

## What must be green before a merge

1. `cd backend && pytest tests/ -q` — 410 passed.
2. `npx tsc --noEmit -p web/tsconfig.app.json` — no errors.
3. `npx tsc --noEmit -p mobile/tsconfig.json` — no errors.

## When the AI drifts

- Reset the session and restate the objective in one sentence.
- Check `aidd_docs/memory/` for current architecture state before assuming.

For the general AIDD playbook, see <https://github.com/ai-driven-dev/framework>.
