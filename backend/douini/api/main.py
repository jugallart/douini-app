from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from douini.api.dependencies import get_db
from douini.api.routes import auth as auth_routes
from douini.api.routes import garmin as garmin_routes
from douini.api.routes import plans as plans_routes
from douini.api.routes import profile as profile_routes
from douini.api.routes import race_results as race_results_routes
from douini.api.routes import sessions as sessions_routes
from douini.api.routes import statistics as statistics_routes
from douini.db.connection import close_pool, open_pool
from douini.settings import configure_logging, settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await open_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Douini Run API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=f"{settings.API_PREFIX}/docs" if settings.DEBUG else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    if settings.is_prod:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    import traceback

    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": traceback.format_exc()},
    )


@app.get(f"{settings.API_PREFIX}/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_routes.router, prefix=settings.API_PREFIX)
app.include_router(profile_routes.router, prefix=settings.API_PREFIX)
app.include_router(plans_routes.router, prefix=settings.API_PREFIX)
app.include_router(sessions_routes.router, prefix=settings.API_PREFIX)
app.include_router(race_results_routes.router, prefix=settings.API_PREFIX)
app.include_router(statistics_routes.router, prefix=settings.API_PREFIX)
app.include_router(garmin_routes.router, prefix=settings.API_PREFIX)
