# Contributing to this project's AI context

How to add or change the context the AI relies on here. For authoring AIDD skills, agents, rules, and templates, see the framework guide: <https://github.com/ai-driven-dev/framework/blob/main/CONTRIBUTING.md>.

## Changing project memory

Add or edit a file under `aidd_docs/memory/`. See [`memory/README.md`](memory/README.md) for what belongs there and how it loads.

Current memory files:
- `architecture.md` — monorepo layout, domain engine, backend layers, database, auth, frontend, Garmin.
- `backend.md` — Python stack, running locally, API structure, key files, gotchas.
- `frontend.md` — Web (React/Vite) and mobile (Expo) structure, shared package.
- `deployment.md` — Docker, Caddy, CI/CD, data migration, backup/restore.
- `decisions.md` — 16 recorded decisions with rationale and status.

## House conventions

- One file per concern in `memory/`. Point to the code, never copy it.
- Current state only. No future TODOs in memory files.
- Decisions go in `decisions.md` with a status (Active/Superseded).
- Plans and task runs go in `tasks/` with a date-prefixed folder.
- The `<aidd_project_memory>` block in `AGENTS.md` is generated from memory files. Update the block when memory files change.
