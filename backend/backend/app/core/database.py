from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_kwargs: dict = {"pool_pre_ping": not _is_sqlite, "echo": settings.is_local}

if _is_sqlite:
    # SQLite-specific settings to handle concurrent access
    _engine_kwargs.update(
        connect_args={
            "timeout": 30,  # 30 second timeout for database locks
            "check_same_thread": False,
        }
    )
else:
    _engine_kwargs.update(pool_size=10, max_overflow=20, pool_recycle=3600)

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for use outside of FastAPI request scope (e.g. Celery tasks)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def task_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for Celery tasks running in their own thread/event loop.

    Creates a fresh engine bound to the current event loop so asyncpg connections
    are never shared with the FastAPI event loop (which would cause
    'attached to a different loop' / 'unknown protocol state' errors in eager mode).
    """
    _settings = get_settings()
    _is_sqlite = _settings.DATABASE_URL.startswith("sqlite")
    _engine_kwargs: dict = {"pool_pre_ping": True}
    if not _is_sqlite:
        _engine_kwargs["pool_size"] = 1
        _engine_kwargs["max_overflow"] = 0
    _task_engine = create_async_engine(_settings.DATABASE_URL, **_engine_kwargs)
    _task_session = async_sessionmaker(
        bind=_task_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    try:
        async with _task_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await _task_engine.dispose()
