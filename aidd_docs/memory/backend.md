# Backend

## Stack

Python 3.14, FastAPI, psycopg3 (async), Alembic, pydantic v2, python-jose, bcrypt, cryptography (Fernet).

## Running locally

```bash
# Postgres
docker compose -f infra/compose.dev.yml up -d

# Migrations
cd backend && alembic upgrade head

# API
cd backend && uvicorn douini.api.main:app --reload --port 8000

# Tests
cd backend && pytest tests/ -q
```

## API structure

Base prefix: `/api/v1`. Health: `GET /api/v1/health`. Docs: `GET /api/v1/docs` (dev only).

Routers: auth, profile, plans, sessions, race_results, statistics, garmin.

All protected routes use `Depends(get_verified_user)` — requires valid JWT + `email_verified=TRUE`.

## Key files

| File | Role |
|------|------|
| `settings.py` | pydantic-settings, env vars, SecretFilter logging |
| `db/connection.py` | AsyncConnectionPool lifecycle, get_conn() |
| `api/dependencies.py` | get_db, get_current_user, get_verified_user |
| `api/schemas.py` | Pydantic v2 request/response models |
| `services/plan.py` | plan_to_json, plan_from_row, generate_plan_service |
| `services/feedback.py` | process_feedback (evaluate_feedback + auto-adjust) |
| `services/race.py` | add_race_result (calc_vdot + profile update) |
| `services/refresh.py` | refresh proposal (plan complete → new vdot/volume) |
| `garmin/builders.py` | workout JSON builders (ported from legacy) |
| `garmin/sync.py` | push/sync plan sessions with Garmin API |

## Gotchas

- **bcrypt**: use `bcrypt` directly, not `passlib`. passlib 1.7.4 breaks with bcrypt 5.0 (`password cannot be longer than 72 bytes` error).
- **JSONB**: psycopg3 returns Python objects for JSONB columns. Guard with `isinstance(x, str)` before `json.loads()`.
- **WorkoutDef**: domain `Session.workout` is `Optional[WorkoutDef]` (dataclass), not a string. Serialize as `.name` for JSON.
- **Email verification**: currently auto-verified on signup (dev mode). Re-enable `send_verification_email` for production.
