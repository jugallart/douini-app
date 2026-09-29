# Douini App

Monorepo for Douini Run v2 — FastAPI backend + React web + Expo mobile.

## Structure

```
backend/     Python FastAPI + PostgreSQL
packages/shared/   TypeScript shared package
web/         React (Vite)
mobile/      Expo (React Native)
```

## Quick start

```bash
npm install
cd backend && pip install -e ".[dev]" && pytest
```
