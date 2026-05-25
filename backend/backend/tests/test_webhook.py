from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import Pod, Request, RequestStatus, RequestType, Severity


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _make_request_with_jira(db: AsyncSession) -> Request:
    import uuid
    req = Request(
        id=uuid.uuid4(),
        title="Jira webhook test",
        request_type=RequestType.FEATURE,
        pod=Pod.CHARGER,
        severity=Severity.HIGH,
        status=RequestStatus.APPROVED,
        business_problem="Testing Jira sync",
        affected_area="Charger firmware",
        submitter_oid="wh-oid",
        submitter_email="wh@test.com",
        submitter_name="Webhook Tester",
        jira_ticket_key="CHG-99",
        jira_ticket_url="https://jira.example.com/browse/CHG-99",
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


@pytest.mark.asyncio
async def test_webhook_jira_status_sync(authed_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request_with_jira(db_session)

    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "CHG-99",
            "fields": {"status": {"name": "In Progress"}},
        },
    }
    body = json.dumps(payload).encode()

    from app.core.config import get_settings
    settings = get_settings()
    headers = {}
    if settings.JIRA_WEBHOOK_SECRET:
        headers["x-hub-signature-256"] = _sign(body, settings.JIRA_WEBHOOK_SECRET)

    resp = await authed_client.post(
        "/api/webhook/jira",
        content=body,
        headers={"content-type": "application/json", **headers},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True


@pytest.mark.asyncio
async def test_webhook_unknown_event_ignored(authed_client: AsyncClient):
    payload = {"webhookEvent": "jira:issue_created"}
    resp = await authed_client.post("/api/webhook/jira", json=payload)
    assert resp.status_code == 200
    assert resp.json()["processed"] is False


@pytest.mark.asyncio
async def test_webhook_no_issue_key(authed_client: AsyncClient):
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"fields": {"status": {"name": "Done"}}},
    }
    resp = await authed_client.post("/api/webhook/jira", json=payload)
    assert resp.status_code == 200
    assert resp.json()["processed"] is False


@pytest.mark.asyncio
async def test_webhook_unknown_ticket_key(authed_client: AsyncClient):
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "UNKNOWN-999",
            "fields": {"status": {"name": "Done"}},
        },
    }
    resp = await authed_client.post("/api/webhook/jira", json=payload)
    assert resp.status_code == 200
    assert resp.json()["processed"] is False
