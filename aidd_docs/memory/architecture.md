# Architecture

## What is Douini

Running training plan generator. VDOT-based pacing, periodized 12-week plans, Garmin workout sync, session feedback loop with auto-adjustment.

Two apps:
- **douini-run** (legacy): NiceGUI monolith at `/Users/jga/Codes/douini-run/`. Still live in production.
- **douini-app** (this repo): FastAPI + React + Expo monorepo. API-first rewrite, reuses legacy domain engine unchanged.

## Monorepo layout

```
douini-app/
  backend/           Python FastAPI (pyproject.toml, alembic/, douini/, tests/)
  packages/shared/   @douini/shared TypeScript (types + API client)
  web/               React 19 + Vite 6 + Tailwind 3.4
  mobile/            Expo SDK 53 + expo-router v4
  infra/             Docker, Caddy, compose, deploy scripts
  .github/           CI/CD workflows
  scripts/           SQLite→PG migration script
  aidd_docs/         AI context, memory, plans
```

## Domain engine (read-only vendor)

Copied from `douini-run/src/douini_run/` into `backend/douini/domain/`. Never modified.

Files: `engine/` (13 modules + data/ + workouts/), `planner.py`, `vdot.py`, `models.py`, `exporters.py`.

410 tests in `backend/tests/` (10 files, pure domain). All must pass before any backend change ships.

Key domain entry points:
- `generate_plan(runner, distance, weeks, ...)` → `TrainingPlan`
- `calc_vdot(distance, time)` → float
- `evaluate_feedback(feedback, workout_name, streak)` → dict
- `PaceEngine(vdot).build_profile().to_paces()` → Paces
- `compute_statistics(sessions, plans, counts)` → dict

## Backend layers

```
douini/
  settings.py        pydantic-settings (env-driven)
  api/                FastAPI app, routes, dependencies, schemas
  auth/               JWT, bcrypt, rate limiting, email/reset tokens
  db/                 psycopg3 async pool + queries/
  garmin/             Fernet crypto, Garmin client, workout builders, sync
  services/           plan, feedback, race, refresh (ports from legacy services.py)
  mailer.py           SMTP transactional emails
  domain/             read-only engine
```

Request flow: route → dependency(get_verified_user) → service → query → psycopg3.

## Database

PostgreSQL 16. psycopg3 async (AsyncConnectionPool). Raw SQL with `%s` placeholders. No ORM.

6 Alembic migrations (001-006): schema, users/auth, profile, plans/sessions/feedback/adjustments/refresh, race_results/vdot_history, garmin_tokens.

JSONB columns: `sessions_json`, `settings_json`, `training_days_json`, `preferred_days_json`, `diff_json`, `proposal_json`. psycopg3 auto-deserializes JSONB to Python objects — never call `json.loads()` on already-deserialized values.

## Auth

JWT (python-jose HS256). Access token 30min, refresh token 30d with rotation. bcrypt direct (not passlib — passlib 1.7.4 incompatible with bcrypt 5.0). Email verification auto-skipped in dev (users marked verified on signup). Rate limiting: in-memory sliding window deque, 5 req/15min per IP.

## Frontend

- Web: React 19 + react-router 7 + TanStack Query 5 + Tailwind 3.4 + Vite 6
- Mobile: Expo SDK 53 + expo-router 4 + TanStack Query 5 + expo-secure-store
- Shared: `@douini/shared` package with TypeScript types + API client (apiFetch with JWT injection, 401→refresh+retry)

## Garmin integration

Per-user Fernet-encrypted tokens in DB. `garminconnect` 0.3.16 + `garth` for session management. Workout builders ported from legacy `garmin.py`. Sync via `asyncio.to_thread` (Garmin API is sync).
