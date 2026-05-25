from __future__ import annotations

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_status = "connected"
    redis_status = "connected"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        db_status = "error"

    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        redis_status = "error"

    return HealthResponse(
        status="ok" if db_status == "connected" and redis_status == "connected" else "degraded",
        db=db_status,
        redis=redis_status,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
