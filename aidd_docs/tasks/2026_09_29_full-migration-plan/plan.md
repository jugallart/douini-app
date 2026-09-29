---
objective: "Build Douini Run v2 as FastAPI + React + Expo, reusing the existing domain engine (5,800 LOC) unchanged, exposing a REST API consumed by a React web app and an Expo mobile app."
status: completed
---

# Plan: Full Stack Migration — FastAPI + React + Expo

## Overview

| Field | Value |
|-------|-------|
| **Goal** | Ship Douini Run v2 : REST API (FastAPI + PostgreSQL) + web (React + Vite) + mobile (Expo), domaine Python réutilisé intact. L'app NiceGUI actuelle reste live dans son repo pendant toute la migration. |
| **Source** | Architecture review (00-overview → 07-saas-roadmap) + migration analysis (06-migration-analysis) |

Le repo actuel n'est jamais modifié. Ce repo est un projet séparé — il fork uniquement le moteur de domaine et construit une architecture API-first par-dessus.

Le moteur de domaine (`engine/`, `planner.py`, `vdot.py`, `models.py`, `exporters.py`) est copié une seule fois en Phase 0 dans `backend/douini/domain/` et traité comme un package vendor read-only. Les 470 tests existants sont portés en Phase 0 et doivent passer avant qu'une autre phase commence.

L'API est une couche service fine par-dessus la logique existante de `services.py`, réimplémentée avec PostgreSQL async et isolation par utilisateur. Le frontend (React + Expo) consomme l'API via un package TypeScript partagé (`@douini/shared`).

**Security gate** : l'app ne doit pas être exposée à des utilisateurs publics avant que la Phase 2 (auth), la Phase 3 (queries user-scopées), et la Phase 4 (tokens Garmin per-user) soient complètes et vérifiées.

## Phases

| # | Phase | File |
|---|-------|------|
| 0 | Bootstrap monorepo + domain copy | [phase-0.md](./phase-0.md) |
| 1 | Backend foundation (FastAPI + PostgreSQL + Alembic) | [phase-1.md](./phase-1.md) |
| 2 | Auth API (JWT + email verify + rate limiting + reset) | [phase-2.md](./phase-2.md) |
| 3 | Core API endpoints (profile, plans, sessions, race, stats) | [phase-3.md](./phase-3.md) |
| 4 | Per-user Garmin (Fernet tokens + sync) | [phase-4.md](./phase-4.md) |
| 5 | @douini/shared TypeScript package | [phase-5.md](./phase-5.md) |
| 6 | Web — auth + wizard | [phase-6.md](./phase-6.md) |
| 7 | Web — dashboard + plan + profile + pantheon + settings | [phase-7.md](./phase-7.md) |
| 8 | Mobile Expo — auth + dashboard + plan + profile | [phase-8.md](./phase-8.md) |
| 9 | Docker + Caddy + PPE deployment | [phase-9.md](./phase-9.md) |
| 10 | CI/CD (GitHub Actions) | [phase-10.md](./phase-10.md) |
| 11 | Production cutover + data migration | [phase-11.md](./phase-11.md) |

## Resources

| Source | Verified |
|--------|----------|
| fastapi.tiangolo.com | Async natif, Pydantic v2, OpenAPI auto |
| www.psycopg.org/psycopg3 | Driver async, placeholders %s, RETURNING id |
| alembic.sqlalchemy.org | Migrations sans ORM |
| python-jose[cryptography] (PyPI) | JWT encode/decode, HS256 |
| passlib[bcrypt] (PyPI) | Hashing bcrypt |
| cryptography.io (Fernet) | Chiffrement tokens Garmin |
| garminconnect 0.3.16 (PyPI) | API Garmin non-officielle |
| garth (PyPI) | Session Garmin, garth.resume() |
| react.dev | React 19, pas de SSR |
| tanstack.com/query/v5 | Server state, background refetch |
| vitejs.dev | Vite 6, bundler + dev server |
| tailwindcss.com v3.4 | Utility CSS |
| reactrouter.com v7 | Data router, nested routes |
| docs.expo.dev (SDK 53) | Expo Router v4, EAS Build |
| docs.expo.dev/guides/using-secure-store | Stockage sécurisé tokens device |
| npmjs.com (workspaces) | npm workspaces natifs |

## Decisions

| Decision | Why |
|----------|-----|
| Fork + repo séparé | L'app NiceGUI est en production ; risque zéro de la casser |
| Domaine engine read-only dans `backend/douini/domain/` | 5 800 LOC, 470 tests, zéro couplage UI — copié une fois, jamais modifié |
| FastAPI over Django/Flask | Async natif, Pydantic v2, OpenAPI automatique, peu de boilerplate |
| psycopg3 raw SQL over ORM | Même style que `db.py` existant ; pas de courbe d'apprentissage ORM ; queries explicites |
| Alembic sans SQLAlchemy ORM | Migrations uniquement, pas de définitions de modèles à maintenir |
| JWT stateless over server sessions | Requis pour le client mobile ; refresh token rotation |
| bcrypt over PBKDF2 | Plus robuste et API plus simple via passlib |
| npm workspaces monorepo | Types TypeScript partagés entre web et mobile sans publication npm |
| React 19 + Vite over Next.js | Pas de SSR nécessaire ; pipeline de build plus simple |
| Expo (managed workflow) over React Native CLI | Solo dev ; EAS Build gère la compilation native |
| TanStack Query pour le server state | Background refetch aligné avec l'UX de sync Garmin |
| Tailwind CSS | IA-friendly à écrire ; zéro runtime ; parité design avec les tokens de `design.py` |
| garminconnect non-officiel | L'API officielle Garmin requiert une entité business |
| Fernet pour les tokens Garmin | Tokens per-user en DB, chiffrés au repos, rotation via clé serveur |
| Pas de Celery/Redis | Les background tasks asyncio de FastAPI suffisent à la cible (dizaines d'utilisateurs) |
| Les tests Phase 0 doivent passer avant Phase 1 | La correction du domaine est le fondement non-négociable |
