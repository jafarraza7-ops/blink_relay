"""End-to-end JSM integration tests — no real network, no real Jira/JSM.

These tests exercise the full lifecycle of a request as JSM sees it:

  submit → comment → status change → approve → dev-ticket created → done → closed

…and assert that every step fires the correct task with the correct payload.
``settings.JIRA_MOCK`` and ``settings.JSM_MOCK`` are forced on by conftest, so
nothing leaves the test process.
"""
from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import (
    Pod,
    Priority,
    Request,
    RequestStatus,
    RequestType,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _seed_request(
    db: AsyncSession,
    submitter_oid: str = "test-oid-1234",
    submitter_email: str = "testuser@blinkcharging.com",
    status: RequestStatus = RequestStatus.SUBMITTED,
    *,
    jsm_ticket_key: str | None = None,
    jira_ticket_key: str | None = None,
) -> Request:
    rid = uuid.uuid4()
    req = Request(
        id=rid,
        reference_id=f"BLR-2026-{str(rid)[:6]}",
        title="EV session export",
        request_type=RequestType.FEATURE,
        pod=Pod.DRIVER,
        priority=Priority.MEDIUM,
        status=status,
        business_problem="Drivers want CSV exports",
        affected_area="Driver app",
        submitter_oid=submitter_oid,
        submitter_email=submitter_email,
        submitter_name="Test User",
        jsm_ticket_key=jsm_ticket_key,
        jira_ticket_key=jira_ticket_key,
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


async def _set_status(db: AsyncSession, req_id: uuid.UUID, status: RequestStatus) -> None:
    result = await db.execute(select(Request).where(Request.id == req_id))
    req = result.scalar_one()
    req.status = status
    await db.flush()


# ── Submission fires JSM ticket creation ──────────────────────────────────────

@pytest.mark.asyncio
async def test_submitting_a_request_fires_jsm_ticket_creation(
    authed_client: AsyncClient,
    sample_request_payload,
    jsm_task_spies,
):
    import asyncio
    resp = await authed_client.post("/api/requests", json=sample_request_payload)
    assert resp.status_code == 201
    request_id = resp.json()["id"]
    # Let asyncio.create_task from the endpoint run
    await asyncio.sleep(0)

    # JSM ticket creation task was queued exactly once with the new request id
    jsm_task_spies["create"].assert_called_once_with(request_id)
    # No comment / close yet
    jsm_task_spies["comment"].assert_not_called()
    jsm_task_spies["close"].assert_not_called()


@pytest.mark.asyncio
async def test_submission_response_exposes_jsm_fields(
    authed_client: AsyncClient,
    sample_request_payload,
):
    resp = await authed_client.post("/api/requests", json=sample_request_payload)
    body = resp.json()
    # Fields are present in the API contract even when null at submission time
    # (the JSM task sets them asynchronously)
    assert "jsm_ticket_key" in body
    assert "jsm_ticket_url" in body
    assert "jsm_resolved_at" in body


# ── Thread messages mirror to JSM as comments ─────────────────────────────────

@pytest.mark.asyncio
async def test_posting_a_message_fires_jsm_comment_task(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    jsm_task_spies,
):
    req = await _seed_request(db_session, jsm_ticket_key="BLR-MOCK01")

    resp = await authed_client.post(
        f"/api/requests/{req.id}/messages",
        json={"body": "Adding more detail about checkout flow", "is_internal": False},
    )
    assert resp.status_code == 201

    jsm_task_spies["comment"].assert_called_once()
    args = jsm_task_spies["comment"].call_args[0]
    assert args[0] == str(req.id)
    assert "Adding more detail about checkout flow" in args[1]
    # public flag = not is_internal
    assert args[2] is True


@pytest.mark.asyncio
async def test_internal_message_posts_private_jsm_comment(
    pm_client: AsyncClient,
    db_session: AsyncSession,
    jsm_task_spies,
):
    req = await _seed_request(db_session, jsm_ticket_key="BLR-MOCK01")

    resp = await pm_client.post(
        f"/api/requests/{req.id}/messages",
        json={"body": "Internal note for reviewers", "is_internal": True},
    )
    assert resp.status_code == 201
    args = jsm_task_spies["comment"].call_args[0]
    assert args[2] is False  # public=False for internal


# ── Status changes log activity to JSM ────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_update_fires_jsm_activity_comment(
    pm_client: AsyncClient,
    db_session: AsyncSession,
    jsm_task_spies,
):
    req = await _seed_request(db_session, jsm_ticket_key="BLR-MOCK02")

    resp = await pm_client.patch(
        f"/api/requests/{req.id}/status",
        json={"status": "InReview", "comment": "Picking this up"},
    )
    assert resp.status_code == 200

    jsm_task_spies["comment"].assert_called_once()
    args = jsm_task_spies["comment"].call_args[0]
    assert args[0] == str(req.id)
    assert "Status changed" in args[1]
    assert "Submitted" in args[1] and "InReview" in args[1]
    assert "Picking this up" in args[1]


@pytest.mark.asyncio
async def test_approval_creates_jira_ticket_and_logs_to_jsm(
    pm_client: AsyncClient,
    db_session: AsyncSession,
    jsm_task_spies,
):
    req = await _seed_request(
        db_session,
        status=RequestStatus.IN_REVIEW,
        jsm_ticket_key="BLR-MOCK03",
    )

    resp = await pm_client.post(f"/api/requests/{req.id}/approve", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Approved"

    # Both the dev-ticket creation AND the JSM activity log were queued
    jsm_task_spies["create_jira"].assert_called_once()
    jsm_task_spies["comment"].assert_called_once()
    args = jsm_task_spies["comment"].call_args[0]
    assert "approved" in args[1].lower()


# ── Rejection auto-closes the JSM ticket ──────────────────────────────────────

@pytest.mark.asyncio
async def test_rejection_closes_jsm_with_reason(
    pm_client: AsyncClient,
    db_session: AsyncSession,
    jsm_task_spies,
):
    req = await _seed_request(
        db_session,
        status=RequestStatus.IN_REVIEW,
        jsm_ticket_key="BLR-MOCK04",
    )

    resp = await pm_client.post(
        f"/api/requests/{req.id}/reject",
        json={"reason": "Out of scope", "comment": "Already on the Q3 roadmap"},
    )
    assert resp.status_code == 200

    jsm_task_spies["close"].assert_called_once()
    args = jsm_task_spies["close"].call_args[0]
    assert args[0] == str(req.id)
    assert "Rejected" in args[1]
    assert "Out of scope" in args[1]
    assert "Already on the Q3 roadmap" in args[1]


# ── Jira webhook (Done) auto-closes the JSM ticket ────────────────────────────

@pytest.mark.asyncio
async def test_jira_webhook_done_closes_jsm(
    anon_client: AsyncClient,
    db_session: AsyncSession,
    jsm_task_spies,
):
    """Simulate a Jira webhook reporting the dev ticket is Done — JSM should close."""
    req = await _seed_request(
        db_session,
        status=RequestStatus.IN_PROGRESS,
        jira_ticket_key="DRV-42",
        jsm_ticket_key="BLR-MOCK05",
    )

    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "DRV-42",
            "fields": {"status": {"name": "Done"}},
        },
    }
    resp = await anon_client.post("/api/webhook/jira", json=payload)
    assert resp.status_code == 200
    assert resp.json()["processed"] is True

    jsm_task_spies["close"].assert_called_once()
    args = jsm_task_spies["close"].call_args[0]
    assert args[0] == str(req.id)
    assert "DRV-42" in args[1]


@pytest.mark.asyncio
async def test_jira_webhook_in_progress_does_not_close_jsm(
    anon_client: AsyncClient,
    db_session: AsyncSession,
    jsm_task_spies,
):
    """Only terminal states close the JSM ticket — not intermediate transitions."""
    req = await _seed_request(
        db_session,
        status=RequestStatus.APPROVED,
        jira_ticket_key="DRV-43",
        jsm_ticket_key="BLR-MOCK06",
    )

    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "DRV-43",
            "fields": {"status": {"name": "In Progress"}},
        },
    }
    resp = await anon_client.post("/api/webhook/jira", json=payload)
    assert resp.status_code == 200

    jsm_task_spies["close"].assert_not_called()


# ── Idempotency at the service level ──────────────────────────────────────────
#
# Task-level idempotency (``jsm_resolved_at`` short-circuit, "JSM ticket already
# exists" guard) is exercised inside the tasks themselves; the webhook tests
# above already verify that the close path fires only once per terminal
# transition. Here we cover the deterministic-mock contract that the JSM service
# returns the same key for the same input — the ground truth our idempotency
# guards rely on.

@pytest.mark.asyncio
async def test_jsm_mock_returns_stable_key_for_same_request(db_session: AsyncSession):
    from app.services.jsm_service import JsmService

    svc = JsmService()
    a = await svc.create_request(
        summary="Same",
        description="x",
        reporter_email="u@e.com",
        reference_id="BLR-2026-0001",
    )
    b = await svc.create_request(
        summary="Same",
        description="x",
        reporter_email="u@e.com",
        reference_id="BLR-2026-0001",
    )
    assert a["key"] == b["key"]


# ── Full lifecycle smoke test ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_request_lifecycle_via_api(
    authed_client: AsyncClient,
    pm_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    sample_request_payload,
    jsm_task_spies,
):
    """End-to-end: submit → message → status → approve → webhook done.

    Asserts that the JSM activity log fires at every meaningful step, and the
    JSM ticket auto-closes once the dev ticket is reported as Done.
    """
    import asyncio
    # 1. Submit
    submit_resp = await authed_client.post("/api/requests", json=sample_request_payload)
    assert submit_resp.status_code == 201
    request_id = submit_resp.json()["id"]
    await asyncio.sleep(0)  # let asyncio.create_task from endpoint run
    jsm_task_spies["create"].assert_called_once_with(request_id)

    # Patch the request in DB so subsequent calls find it (the test client uses
    # its own session). Set jsm_ticket_key to simulate the create-task running.
    result = await db_session.execute(select(Request).where(Request.id == uuid.UUID(request_id)))
    req = result.scalar_one()
    req.jsm_ticket_key = "BLR-MOCKZZ"
    req.jsm_ticket_url = "https://example/portal/BLR-MOCKZZ"
    await db_session.commit()

    # 2. Reviewer adds a thread message → JSM comment fires
    msg_resp = await pm_client.post(
        f"/api/requests/{request_id}/messages",
        json={"body": "Got it — picking this up", "is_internal": False},
    )
    assert msg_resp.status_code == 201
    assert jsm_task_spies["comment"].call_count == 1

    # 3. PM moves to InReview
    status_resp = await pm_client.patch(
        f"/api/requests/{request_id}/status",
        json={"status": "InReview"},
    )
    assert status_resp.status_code == 200
    assert jsm_task_spies["comment"].call_count == 2

    # 4. PM approves → dev ticket creation + JSM activity comment
    approve_resp = await pm_client.post(f"/api/requests/{request_id}/approve", json={})
    assert approve_resp.status_code == 200
    jsm_task_spies["create_jira"].assert_called_once()
    assert jsm_task_spies["comment"].call_count == 3

    # 5. Simulate the dev ticket being marked Done via webhook → JSM closes
    # Set jira_ticket_key directly so the webhook can find the request
    result = await db_session.execute(select(Request).where(Request.id == uuid.UUID(request_id)))
    req = result.scalar_one()
    req.jira_ticket_key = "DRV-555"
    req.status = RequestStatus.IN_PROGRESS  # webhook will transition this
    await db_session.commit()

    webhook_resp = await anon_client.post(
        "/api/webhook/jira",
        json={
            "webhookEvent": "jira:issue_updated",
            "issue": {"key": "DRV-555", "fields": {"status": {"name": "Done"}}},
        },
    )
    assert webhook_resp.status_code == 200
    jsm_task_spies["close"].assert_called_once()
    close_args = jsm_task_spies["close"].call_args[0]
    assert close_args[0] == request_id
    assert "DRV-555" in close_args[1]
