"""
main.py — FastAPI application entry point for Blink Relay.

Responsibilities:
- Runs Alembic migrations on every startup (idempotent; safe for rolling deploys).
- Verifies DB and Redis connectivity before accepting traffic.
- Registers all API routers under the /api prefix.
- Configures CORS to allow the React frontend (and localhost dev server).
- Disables Swagger/ReDoc in non-local environments to avoid exposing internals.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, files, health, requests, thread, webhook, workflow
from app.core.config import get_settings
from app.core.database import engine
from app.core.insights import setup_insights

logger = logging.getLogger(__name__)
settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.is_local else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown tasks for the FastAPI app."""
    # ── Startup ──────────────────────────────────────────────────────────────
    setup_insights()
    logger.info("Starting Blink Relay API v%s [%s]", settings.APP_VERSION, settings.ENVIRONMENT)

    # Run Alembic migrations at startup so the DB schema is always current.
    # Safe to run on every start: Alembic is idempotent on already-applied versions.
    try:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, check=True,
        )
        logger.info("Alembic: %s", result.stdout.strip() or "no new migrations")
    except subprocess.CalledProcessError as exc:
        logger.error("Alembic stdout: %s", exc.stdout)
        logger.error("Alembic stderr: %s", exc.stderr)
        logger.exception("Alembic migration failed — aborting startup")
        raise

    # Verify DB connectivity
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified")

    # Verify Redis connectivity (non-fatal in local mode when CELERY_TASK_ALWAYS_EAGER=True)
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        await redis_client.aclose()
        logger.info("Redis connection verified")
    except Exception:
        if settings.is_local and settings.CELERY_TASK_ALWAYS_EAGER:
            logger.warning("Redis unavailable — running in eager mode without broker")
        else:
            raise

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    await engine.dispose()
    logger.info("Blink Relay API shutdown complete")


app = FastAPI(
    title="Blink Relay API",
    description="Internal tech request intake and management system for Blink Network",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.is_local else None,   # disable Swagger in prod
    redoc_url="/redoc" if settings.is_local else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = [settings.FRONTEND_URL, "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)                          # /health (no prefix)
app.include_router(auth.router,     prefix="/api")         # /api/auth/me
app.include_router(requests.router, prefix="/api")         # /api/requests
app.include_router(workflow.router, prefix="/api")         # /api/requests/{id}/...
app.include_router(thread.router,   prefix="/api")         # /api/requests/{id}/messages
app.include_router(files.router,    prefix="/api")         # /api/requests/{id}/files
app.include_router(webhook.router,  prefix="/api")         # /api/webhook/jira
