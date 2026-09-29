---
status: pending
---

# Instruction: Backend Foundation (FastAPI + PostgreSQL + Alembic)

## Architecture projection

> Tree of the final files. ✅ create · ✏️ modify · ❌ delete

```txt
backend/
  pyproject.toml                      ✏️ modify  — ajouter FastAPI, psycopg, alembic, uvicorn
  requirements.lock                   ✅ create  — lock file pour builds reproductibles
  alembic.ini                         ✅ create
  alembic/
    env.py                            ✅ create
    versions/
      001_initial_schema.py           ✅ create  — migration vide, tables ajoutées par phase
  douini/
    settings.py                       ✅ create  — config env-driven, fail-closed, logging structuré
    api/
      __init__.py                     ✅ create
      main.py                         ✅ create  — FastAPI app, lifespan, CORS, health, exception handlers
      dependencies.py                 ✅ create  — get_db() dependency
    db/
      __init__.py                     ✅ create
      connection.py                   ✅ create  — pool PostgreSQL async (psycopg3)
infra/
  compose.dev.yml                     ✅ create  — PostgreSQL 16 uniquement, dev local
.env.example                          ✏️ modify  — ajouter DATABASE_URL, SECRET_KEY, ENVIRONMENT
```

## User Journey

```mermaid
flowchart TD
  A[Copier .env.example vers .env] --> B[Exporter DATABASE_URL + SECRET_KEY]
  B --> C[docker compose -f infra/compose.dev.yml up -d]
  C --> D[cd backend && alembic upgrade head]
  D --> E[uvicorn douini.api.main:app --reload]
  E --> F[GET /api/v1/health → 200 OK]
  F --> G[GET /api/v1/docs → OpenAPI UI en dev]
```

## Test Scope

```mermaid
---
title: Test scope
---
journey
  section Settings
    ENVIRONMENT=dev DATABASE_URL valide => settings chargés: 5: cli
    SECRET_KEY absent en prod => ValueError avant bind: 1: cli
    DATABASE_URL invalide => ValueError au démarrage: 1: cli
    Niveau de log selon ENVIRONMENT => DEBUG en dev, INFO+JSON en prod: 5: cli
  section Database
    alembic upgrade head => migration sans erreur: 5: cli
    alembic downgrade -1 => rollback propre: 5: cli
    get_db() yields connection => SELECT 1 s'exécute: 5: test
  section API
    GET /api/v1/health => 200 status ok version environment: 5: api
    GET /api/v1/docs en dev => 200 HTML Swagger: 5: api
    GET /api/v1/docs en prod => 404: 1: api
    GET /api/v1/openapi.json => 200 JSON schema valide: 5: api
    Requête endpoint inexistant => 404 format JSON uniforme: 1: api
    Exception non gérée en prod => 500 sans stacktrace: 1: api
```

## Tasks to do

### `1)` Mettre à jour pyproject.toml avec les dépendances backend

> Ajouter les deps core pour faire tourner FastAPI + PostgreSQL + Alembic.

1. Ajouter dans [project].dependencies : `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `psycopg[binary]>=3.2`, `psycopg-pool>=3.2`, `alembic>=1.13`, `pydantic-settings>=2.3`, `python-multipart>=0.0.9`.
2. Ajouter [project.optional-dependencies] section dev : `pytest>=8`, `pytest-asyncio>=0.24`, `httpx>=0.27`.
3. Ajouter [tool.pytest.ini_options] avec `testpaths = ["tests"]` et `pythonpath = ["."]`.

### `2)` Créer settings.py

> Config env-driven, fail-closed, plus logging structuré selon environnement.

1. Utiliser pydantic-settings `BaseSettings` pour lire depuis l'environnement.
2. Champs : `ENVIRONMENT: Literal["dev", "ppe", "prod"] = "dev"`, `DATABASE_URL: str`, `SECRET_KEY: str`, `DEBUG: bool = False`, `API_PREFIX: str = "/api/v1"`, `ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8081"]`.
3. Dans un `model_validator(mode="after")` : si `ENVIRONMENT in ("ppe", "prod")` et `SECRET_KEY` fait moins de 32 caractères, lever `ValueError("SECRET_KEY must be at least 32 chars in ppe/prod")`.
4. Exporter un singleton `settings = Settings()` au niveau module.
5. Ne jamais logger `SECRET_KEY` ou `DATABASE_URL`.
6. Configurer `logging.basicConfig` selon `ENVIRONMENT` : format lisible en dev, format JSON en ppe/prod. Niveau depuis `settings.DEBUG` (DEBUG→DEBUG, sinon INFO). Ajouter un filtre qui exclut les valeurs de `SECRET_KEY`, `DATABASE_URL`, et `DOUINI_ENCRYPTION_KEY` des logs.

### `3)` Créer db/connection.py

> Pool PostgreSQL async via psycopg3.

1. Utiliser `psycopg_pool.AsyncConnectionPool` initialisé via le lifespan FastAPI.
2. Exposer `get_pool() -> AsyncConnectionPool` et `get_conn()` comme context manager async yielding une `AsyncConnection`.
3. Toutes les queries utilisent des placeholders `%s` (style psycopg3).
4. Configurer `autocommit=False` par défaut ; les routes commitent explicitement.

### `4)` Créer api/main.py

> FastAPI app avec lifespan, CORS, health, exception handlers globaux.

1. Définir le context manager `lifespan` : ouvrir le pool DB au startup, fermer au shutdown.
2. Créer `app = FastAPI(title="Douini Run API", version="2.0.0", lifespan=lifespan, docs_url=docs_url, redoc_url=None)` où `docs_url="/api/v1/docs"` en dev, `None` en ppe/prod.
3. Ajouter `CORSMiddleware` : `allow_origins=settings.ALLOWED_ORIGINS`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.
4. Monter le router à `settings.API_PREFIX`.
5. Endpoint `GET /api/v1/health` retournant `{"status": "ok", "version": "2.0.0", "environment": settings.ENVIRONMENT}`.
6. Ajouter `app.add_exception_handler(RequestValidationError, ...)` : retourne 422 avec un format JSON homogène `{"detail": [...], "type": "validation_error"}`.
7. Ajouter `app.add_exception_handler(HTTPException, ...)` : format JSON consistant `{"detail": str(exc.detail), "type": "http_error"}`.
8. Ajouter `app.add_exception_handler(Exception, ...)` : en prod, retourne 500 `{"detail": "Internal server error", "type": "server_error"}` sans stacktrace. En dev, logger la stacktrace pour le débogage.

### `5)` Créer api/dependencies.py

> Dependency standard pour tous les handlers de routes.

1. Définir `async def get_db() -> AsyncGenerator[AsyncConnection, None]` : `async with pool.connection() as conn: yield conn`.

### `6)` Configurer Alembic

> Migrations de schéma sans ORM SQLAlchemy.

1. Créer `backend/alembic.ini` (standard Alembic, `script_location = alembic`).
2. Dans `backend/alembic/env.py` : lire `DATABASE_URL` depuis settings ; configurer `context.configure()` avec `compare_type=True`, `compare_server_default=True`.
3. Créer `backend/alembic/versions/001_initial_schema.py` avec `upgrade()` et `downgrade()` vides — les tables sont ajoutées par phase.
4. Vérifier : `alembic upgrade head` s'exécute sans erreur ; `alembic downgrade -1` rollback proprement.

### `7)` Créer infra/compose.dev.yml

> PostgreSQL 16 pour dev local.

1. Un seul service `postgres` : image `postgres:16-alpine`, variables d'env `POSTGRES_DB=douini`, `POSTGRES_USER=douini`, `POSTGRES_PASSWORD=douini`, port `5432:5432`, volume nommé `pgdata_dev`.
2. Health check : `pg_isready -U douini`.

### `8)` Mettre à jour .env.example

> Documenter toutes les vars nécessaires.

1. Ajouter : `ENVIRONMENT=dev`, `DEBUG=true`, `SECRET_KEY=changeme-generate-with-openssl-rand-hex-32`, `DATABASE_URL=postgresql+psycopg://douini:douini@localhost:5432/douini`.
2. Ajouter `ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8081`.
3. Documenter : "Générer SECRET_KEY avec `openssl rand -hex 32`. Ne jamais committer la vraie valeur."

### `9)` Générer requirements.lock

> Lock file pour builds reproductibles.

1. Depuis un venv propre : `pip install -e backend/` puis `pip freeze > backend/requirements.lock`.
2. Versionner le fichier dans le repo.
3. Le Dockerfile (phase 9) utilisera `pip install --require-hashes -r requirements.lock`.

## Test acceptance criteria

| Task | Acceptance criteria |
| ---- | ------------------- |
| 1 | pyproject.toml contient toutes les deps core ; `pip install -e backend/` réussit |
| 2 | `from douini.settings import settings` réussit ; SECRET_KEY absent en prod lève ValueError ; logging configuré selon ENVIRONMENT avec filtre anti-secrets |
| 3 | `get_conn()` yield une connexion psycopg3 fonctionnelle ; SELECT 1 s'exécute |
| 4 | GET /api/v1/health retourne 200 ; /api/v1/docs accessible en dev, 404 en prod ; exception handlers retournent un format JSON uniforme (422, 500 sans stacktrace en prod) |
| 5 | `get_db()` utilisable comme `Depends(get_db)` dans un handler de route |
| 6 | `alembic upgrade head` + `alembic downgrade -1` réussissent tous les deux |
| 7 | `docker compose -f infra/compose.dev.yml up -d` démarre PostgreSQL ; connexion psql confirme |
| 8 | `.env.example` documente toutes les vars avec guidance prod |
| 9 | `backend/requirements.lock` versionné ; `pip install --require-hashes -r requirements.lock` réussit dans un venv propre |
