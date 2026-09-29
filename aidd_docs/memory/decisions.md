# Decisions

| Decision | Why | Status |
|----------|-----|--------|
| Fork + separate repo | Legacy NiceGUI app is in production; zero risk to it | Active |
| Domain engine read-only in `backend/douini/domain/` | 5,800 LOC, 410 tests, zero UI coupling — copied once, never modified | Active |
| FastAPI over Django/Flask | Async native, Pydantic v2, OpenAPI auto, minimal boilerplate | Active |
| psycopg3 raw SQL over ORM | Same style as legacy `db.py`; no ORM learning curve; explicit queries | Active |
| Alembic without SQLAlchemy ORM | Migrations only, no model definitions to maintain | Active |
| JWT stateless | Required for mobile client; refresh token rotation | Active |
| bcrypt direct (not passlib) | passlib 1.7.4 incompatible with bcrypt 5.0 | Active — changed from original plan |
| npm workspaces monorepo | Shared TS types between web and mobile without npm publish | Active |
| React 19 + Vite over Next.js | No SSR needed; simpler build pipeline | Active |
| Expo managed workflow | Solo dev; EAS Build handles native compilation | Active |
| TanStack Query for server state | Background refetch aligned with Garmin sync UX | Active |
| Tailwind CSS | AI-friendly; zero runtime; design token parity | Active |
| garminconnect unofficial | Official Garmin API requires business entity | Active |
| Fernet for Garmin tokens | Per-user tokens encrypted at rest, server-side key rotation | Active |
| No Celery/Redis | asyncio background tasks sufficient for target scale (dozens of users) | Active |
| Email verification auto-skipped in dev | SMTP not configured locally; users verified on signup | Active — re-enable for prod |
