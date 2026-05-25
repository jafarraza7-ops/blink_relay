from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import User


@pytest.mark.asyncio
async def test_get_me(authed_client: AsyncClient, requestor_user):
    resp = await authed_client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["oid"] == requestor_user.oid
    assert data["email"] == requestor_user.email
    assert data["name"] == requestor_user.name


@pytest.mark.asyncio
async def test_sync_creates_user(authed_client: AsyncClient, db_session: AsyncSession, requestor_user):
    resp = await authed_client.post("/api/auth/sync")
    assert resp.status_code == 200

    result = await db_session.execute(select(User).where(User.oid == requestor_user.oid))
    db_user = result.scalar_one_or_none()
    assert db_user is not None
    assert db_user.email == requestor_user.email
    assert db_user.display_name == requestor_user.name


@pytest.mark.asyncio
async def test_sync_updates_existing_user(authed_client: AsyncClient, db_session: AsyncSession, requestor_user):
    # Create first
    await authed_client.post("/api/auth/sync")

    # Update - just call again (same data is fine, verifies no duplicate)
    resp = await authed_client.post("/api/auth/sync")
    assert resp.status_code == 200

    result = await db_session.execute(select(User).where(User.oid == requestor_user.oid))
    users = result.scalars().all()
    # Should not create duplicates
    assert len(users) == 1


@pytest.mark.asyncio
async def test_get_me_returns_roles(authed_client: AsyncClient, requestor_user):
    resp = await authed_client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert "Requestor" in data["roles"]
