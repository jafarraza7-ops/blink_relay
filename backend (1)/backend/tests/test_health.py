from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_health_check_degraded(app):
    """When DB/Redis are unavailable, health returns degraded."""
    from httpx import ASGITransport, AsyncClient as _Client

    with (
        patch("app.api.health.engine") as mock_engine,
        patch("app.api.health.aioredis.from_url") as mock_redis_factory,
    ):
        # DB fails
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute = AsyncMock(side_effect=Exception("DB unavailable"))
        mock_engine.connect.return_value = mock_conn

        # Redis fails
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Redis unavailable"))
        mock_redis.aclose = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        async with _Client(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["db"] == "error"
    assert data["redis"] == "error"


@pytest.mark.asyncio
async def test_health_check_ok(app):
    from httpx import ASGITransport, AsyncClient as _Client

    with (
        patch("app.api.health.engine") as mock_engine,
        patch("app.api.health.aioredis.from_url") as mock_redis_factory,
    ):
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute = AsyncMock(return_value=MagicMock())
        mock_engine.connect.return_value = mock_conn

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        async with _Client(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["redis"] == "connected"
    assert "version" in data
