from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import Request, RequestStatus


async def _create_request_in_db(db: AsyncSession, submitter_oid: str = "test-oid") -> Request:
    """Create a request directly in DB to avoid client-sharing issues."""
    import uuid
    from app.models.request import RequestType, Pod, Priority

    req = Request(
        id=uuid.uuid4(),
        title="Test request for workflow",
        request_type=RequestType.FEATURE,
        pod=Pod.DRIVER,
        priority=Priority.MEDIUM,
        status=RequestStatus.SUBMITTED,
        business_problem="Testing the workflow state machine",
        affected_area="Driver app",
        submitter_oid=submitter_oid,
        submitter_email="test@blinkcharging.com",
        submitter_name="Test User",
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


async def _set_status(db: AsyncSession, request_id, new_status: RequestStatus) -> None:
    from sqlalchemy import select
    result = await db.execute(select(Request).where(Request.id == request_id))
    req = result.scalar_one()
    req.status = new_status
    await db.flush()


@pytest.mark.asyncio
async def test_approve_request(pm_client: AsyncClient, db_session: AsyncSession):
    req = await _create_request_in_db(db_session)
    await _set_status(db_session, req.id, RequestStatus.IN_REVIEW)

    resp = await pm_client.post(f"/api/requests/{req.id}/approve", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Approved"


@pytest.mark.asyncio
async def test_approve_requires_pm_role(reviewer_client: AsyncClient, db_session: AsyncSession):
    req = await _create_request_in_db(db_session)
    await _set_status(db_session, req.id, RequestStatus.IN_REVIEW)

    resp = await reviewer_client.post(f"/api/requests/{req.id}/approve", json={})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reject_request(pm_client: AsyncClient, db_session: AsyncSession):
    req = await _create_request_in_db(db_session)
    await _set_status(db_session, req.id, RequestStatus.IN_REVIEW)

    resp = await pm_client.post(
        f"/api/requests/{req.id}/reject",
        json={"reason": "OutOfScope", "comment": "Not aligned with Q3 priorities."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Rejected"


@pytest.mark.asyncio
async def test_invalid_status_transition_approve(pm_client: AsyncClient, db_session: AsyncSession):
    req = await _create_request_in_db(db_session)
    # First approval succeeds (Submitted → Approved is valid)
    resp = await pm_client.post(f"/api/requests/{req.id}/approve", json={})
    assert resp.status_code == 200
    # Second approval is invalid (Approved → Approved is not in ALLOWED_TRANSITIONS)
    resp = await pm_client.post(f"/api/requests/{req.id}/approve", json={})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_patch_status_valid_transition(reviewer_client: AsyncClient, db_session: AsyncSession):
    req = await _create_request_in_db(db_session)

    resp = await reviewer_client.patch(
        f"/api/requests/{req.id}/status",
        json={"status": "InReview"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "InReview"


@pytest.mark.asyncio
async def test_patch_status_invalid_transition(reviewer_client: AsyncClient, db_session: AsyncSession):
    req = await _create_request_in_db(db_session)
    # Submitted → InProgress is not valid

    resp = await reviewer_client.patch(
        f"/api/requests/{req.id}/status",
        json={"status": "InProgress"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_approve_already_approved(pm_client: AsyncClient, db_session: AsyncSession):
    req = await _create_request_in_db(db_session)
    await _set_status(db_session, req.id, RequestStatus.APPROVED)

    resp = await pm_client.post(f"/api/requests/{req.id}/approve", json={})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_workflow_not_found(pm_client: AsyncClient):
    resp = await pm_client.post(
        "/api/requests/00000000-0000-0000-0000-000000000000/approve", json={}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_allowed_transitions_complete_path(pm_client: AsyncClient, db_session: AsyncSession):
    """Full happy-path using PM (who can also do InReview transition): Submitted → InReview → Approved."""
    req = await _create_request_in_db(db_session)

    patch_resp = await pm_client.patch(
        f"/api/requests/{req.id}/status", json={"status": "InReview"}
    )
    assert patch_resp.status_code == 200

    approve_resp = await pm_client.post(f"/api/requests/{req.id}/approve", json={})
    assert approve_resp.status_code == 200
