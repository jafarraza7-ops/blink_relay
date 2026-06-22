from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import (
    Pod, Priority, Request, RequestStatus, RequestType, )


async def _make_request(db: AsyncSession) -> Request:
    import uuid
    req = Request(
        id=uuid.uuid4(),
        title="Thread test request",
        request_type=RequestType.FEATURE,
        pod=Pod.DATA,
        priority=Priority.LOW,
        status=RequestStatus.SUBMITTED,
        business_problem="Testing message thread",
        affected_area="Dashboard",
        submitter_oid="test-oid-1234",
        submitter_email="testuser@blinkcharging.com",
        submitter_name="Thread Tester",
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


@pytest.mark.asyncio
async def test_post_message(authed_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request(db_session)
    resp = await authed_client.post(
        f"/api/requests/{req.id}/messages",
        json={"body": "Please review this request."},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["body"] == "Please review this request."
    assert data["is_internal"] is False
    assert data["author_email"] == "testuser@blinkcharging.com"


@pytest.mark.asyncio
async def test_post_internal_message(pm_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request(db_session)
    resp = await pm_client.post(
        f"/api/requests/{req.id}/messages",
        json={"body": "Internal note for review team.", "is_internal": True},
    )
    assert resp.status_code == 201
    assert resp.json()["is_internal"] is True


@pytest.mark.asyncio
async def test_list_messages(authed_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request(db_session)
    await authed_client.post(
        f"/api/requests/{req.id}/messages", json={"body": "First message"}
    )
    await authed_client.post(
        f"/api/requests/{req.id}/messages", json={"body": "Second message"}
    )

    resp = await authed_client.get(f"/api/requests/{req.id}/messages")
    assert resp.status_code == 200
    messages = resp.json()
    assert len(messages) >= 2


@pytest.mark.asyncio
async def test_post_message_request_not_found(authed_client: AsyncClient):
    resp = await authed_client.post(
        "/api/requests/00000000-0000-0000-0000-000000000000/messages",
        json={"body": "test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_messages_request_not_found(authed_client: AsyncClient):
    resp = await authed_client.get(
        "/api/requests/00000000-0000-0000-0000-000000000000/messages"
    )
    assert resp.status_code == 404
