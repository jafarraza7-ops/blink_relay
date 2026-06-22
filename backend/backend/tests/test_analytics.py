"""Tests for analytics endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert

from app.models.request import Request, RequestStatus, RequestType, Pod


async def _clean_requests(db_session):
    """Delete all requests so analytics counts start from zero."""
    await db_session.execute(delete(Request))
    await db_session.commit()


@pytest.mark.asyncio
async def test_request_aging_requires_pm_or_reviewer(authed_client):
    """Only PMs and reviewers can access request aging endpoint."""
    response = await authed_client.get("/api/analytics/request-aging")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_request_aging_empty(pm_client, db_session):
    """Request aging endpoint returns zero counts when no requests exist."""
    await _clean_requests(db_session)

    response = await pm_client.get("/api/analytics/request-aging")
    assert response.status_code == 200
    data = response.json()

    assert data["fresh"]["count"] == 0
    assert data["aging"]["count"] == 0
    assert data["stale"]["count"] == 0
    assert data["stale_requests"] == []


@pytest.mark.asyncio
async def test_request_aging_categorizes_correctly(pm_client, db_session):
    """Request aging correctly categorizes requests into buckets."""
    await _clean_requests(db_session)
    now = datetime.now(timezone.utc)
    run_id = str(uuid4())[:8]

    # Create fresh request (updated 10 days ago)
    fresh_req = Request(
        id=uuid4(),
        reference_id=f"BLR-{run_id}-1",
        title="Fresh request",
        submitter_email="user@example.com",
        pod=Pod.CHARGER,
        request_type=RequestType.FEATURE,
        status=RequestStatus.SUBMITTED,
        created_at=now - timedelta(days=20),
        updated_at=now - timedelta(days=10),
    )

    # Create aging request (updated 45 days ago)
    aging_req = Request(
        id=uuid4(),
        reference_id=f"BLR-{run_id}-2",
        title="Aging request",
        submitter_email="user@example.com",
        pod=Pod.DRIVER,
        request_type=RequestType.FEATURE,
        status=RequestStatus.IN_REVIEW,
        created_at=now - timedelta(days=50),
        updated_at=now - timedelta(days=45),
    )

    # Create stale request (updated 70 days ago)
    stale_req = Request(
        id=uuid4(),
        reference_id=f"BLR-{run_id}-3",
        title="Stale request",
        submitter_email="user@example.com",
        pod=Pod.REVENUE,
        request_type=RequestType.FEATURE,
        status=RequestStatus.AWAITING_INFO,
        created_at=now - timedelta(days=80),
        updated_at=now - timedelta(days=70),
    )

    # Insert requests directly
    _defaults = {"business_problem": "Test", "affected_area": "Test", "submitter_oid": "analytics-oid", "submitter_name": "Analytics Tester"}
    await db_session.execute(
        insert(Request).values([
            {
                "id": fresh_req.id,
                "reference_id": fresh_req.reference_id,
                "title": fresh_req.title,
                "submitter_email": fresh_req.submitter_email,
                "pod": fresh_req.pod,
                "request_type": fresh_req.request_type,
                "status": fresh_req.status,
                "created_at": fresh_req.created_at,
                "updated_at": fresh_req.updated_at,
                **_defaults,
            },
            {
                "id": aging_req.id,
                "reference_id": aging_req.reference_id,
                "title": aging_req.title,
                "submitter_email": aging_req.submitter_email,
                "pod": aging_req.pod,
                "request_type": aging_req.request_type,
                "status": aging_req.status,
                "created_at": aging_req.created_at,
                "updated_at": aging_req.updated_at,
                **_defaults,
            },
            {
                "id": stale_req.id,
                "reference_id": stale_req.reference_id,
                "title": stale_req.title,
                "submitter_email": stale_req.submitter_email,
                "pod": stale_req.pod,
                "request_type": stale_req.request_type,
                "status": stale_req.status,
                "created_at": stale_req.created_at,
                "updated_at": stale_req.updated_at,
                **_defaults,
            },
        ])
    )
    await db_session.commit()

    response = await pm_client.get("/api/analytics/request-aging")
    assert response.status_code == 200
    data = response.json()

    # Verify bucket counts
    assert data["fresh"]["count"] == 1
    assert data["aging"]["count"] == 1
    assert data["stale"]["count"] == 1

    # Verify bucket labels
    assert data["fresh"]["label"] == "0-30 days"
    assert data["aging"]["label"] == "30-60 days"
    assert data["stale"]["label"] == "60+ days"


@pytest.mark.asyncio
async def test_request_aging_stale_requests_sorted(pm_client, db_session):
    """Top 5 stale requests are returned sorted by age (oldest first)."""
    await _clean_requests(db_session)
    now = datetime.now(timezone.utc)
    run_id = str(uuid4())[:8]

    # Create 7 stale requests
    stale_reqs = []
    for i in range(7):
        days_old = 65 + (i * 5)  # 65, 70, 75, 80, 85, 90, 95 days
        req = Request(
            id=uuid4(),
            reference_id=f"BLR-{run_id}-{i}",
            title=f"Stale request {i}",
            submitter_email="user@example.com",
            pod=Pod.CHARGER,
            request_type=RequestType.FEATURE,
            status=RequestStatus.AWAITING_INFO,
            created_at=now - timedelta(days=days_old + 10),
            updated_at=now - timedelta(days=days_old),
        )
        stale_reqs.append(req)

    _defaults = {"business_problem": "Test", "affected_area": "Test", "submitter_oid": "analytics-oid", "submitter_name": "Analytics Tester"}
    # Insert all requests
    await db_session.execute(
        insert(Request).values([
            {
                "id": req.id,
                "reference_id": req.reference_id,
                "title": req.title,
                "submitter_email": req.submitter_email,
                "pod": req.pod,
                "request_type": req.request_type,
                "status": req.status,
                "created_at": req.created_at,
                "updated_at": req.updated_at,
                **_defaults,
            }
            for req in stale_reqs
        ])
    )
    await db_session.commit()

    response = await pm_client.get("/api/analytics/request-aging")
    assert response.status_code == 200
    data = response.json()

    # Only top 5 stale requests returned
    assert len(data["stale_requests"]) == 5

    # Verify they're sorted by age (oldest first = lowest updated_at)
    for i, stale_req in enumerate(data["stale_requests"]):
        expected_days = 95 - (i * 5)  # 95, 90, 85, 80, 75
        assert stale_req["days_idle"] == expected_days


@pytest.mark.asyncio
async def test_request_aging_stale_request_fields(pm_client, db_session):
    """Stale request response includes all required fields."""
    await _clean_requests(db_session)
    now = datetime.now(timezone.utc)
    run_id = str(uuid4())[:8]

    req = Request(
        id=uuid4(),
        reference_id=f"BLR-{run_id}-5",
        title="Test stale request",
        submitter_email="user@example.com",
        pod=Pod.DATA,
        request_type=RequestType.FEATURE,
        status=RequestStatus.IN_REVIEW,
        created_at=now - timedelta(days=75),
        updated_at=now - timedelta(days=70),
    )

    await db_session.execute(
        insert(Request).values({
            "id": req.id,
            "reference_id": req.reference_id,
            "title": req.title,
            "submitter_email": req.submitter_email,
            "pod": req.pod,
            "request_type": req.request_type,
            "status": req.status,
            "created_at": req.created_at,
            "updated_at": req.updated_at,
            "business_problem": "Test",
            "affected_area": "Test",
            "submitter_oid": "analytics-oid",
            "submitter_name": "Analytics Tester",
        })
    )
    await db_session.commit()

    response = await pm_client.get("/api/analytics/request-aging")
    assert response.status_code == 200
    data = response.json()

    assert len(data["stale_requests"]) == 1
    stale_req = data["stale_requests"][0]

    # Verify all fields are present
    assert "id" in stale_req
    assert "reference_id" in stale_req
    assert "title" in stale_req
    assert "status" in stale_req
    assert "days_idle" in stale_req
    assert "pod" in stale_req

    # Verify values
    assert stale_req["reference_id"] == "BLR-5555"
    assert stale_req["title"] == "Test stale request"
    assert stale_req["status"] == "IN_REVIEW"
    assert stale_req["pod"] == "DATA"
    assert stale_req["days_idle"] == 70


@pytest.mark.asyncio
async def test_request_aging_reviewer_can_access(reviewer_client, db_session):
    """Pod reviewers can also access request aging endpoint."""
    response = await reviewer_client.get("/api/analytics/request-aging")
    assert response.status_code == 200
    data = response.json()

    # Should return valid structure
    assert "fresh" in data
    assert "aging" in data
    assert "stale" in data
    assert "stale_requests" in data
