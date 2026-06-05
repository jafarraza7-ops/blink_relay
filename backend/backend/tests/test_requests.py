from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_request_authenticated(authed_client: AsyncClient, sample_request_payload):
    resp = await authed_client.post("/api/requests", json=sample_request_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == sample_request_payload["title"]
    assert data["status"] == "Submitted"
    assert data["pod"] == "Driver"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_request_anonymous(anon_client: AsyncClient, sample_request_payload):
    resp = await anon_client.post("/api/requests", json=sample_request_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["submitter_email"] == "unknown@external"


@pytest.mark.asyncio
async def test_create_request_validation_error(authed_client: AsyncClient):
    resp = await authed_client.post("/api/requests", json={"title": "hi"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_request_public(anon_client: AsyncClient, sample_request_payload):
    # anon users can POST (public) and GET (public)
    create = await anon_client.post("/api/requests", json=sample_request_payload)
    assert create.status_code == 201
    request_id = create.json()["id"]

    resp = await anon_client.get(f"/api/requests/{request_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == request_id


@pytest.mark.asyncio
async def test_get_request_not_found(anon_client: AsyncClient):
    resp = await anon_client.get("/api/requests/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_requests_requires_reviewer(authed_client: AsyncClient):
    resp = await authed_client.get("/api/requests")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_requests_reviewer_can_access(reviewer_client: AsyncClient, sample_request_payload):
    await reviewer_client.post("/api/requests", json=sample_request_payload)
    resp = await reviewer_client.get("/api/requests")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_requests_filter_by_pod(reviewer_client: AsyncClient, sample_request_payload):
    await reviewer_client.post("/api/requests", json=sample_request_payload)
    resp = await reviewer_client.get("/api/requests?pod=Driver")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["pod"] == "Driver"


@pytest.mark.asyncio
async def test_respond_to_request(anon_client: AsyncClient, sample_request_payload, db_session):
    import uuid as _uuid
    from app.models.request import Request, RequestStatus
    from sqlalchemy import select

    create = await anon_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]

    # Manually set status to AwaitingInfo
    result = await db_session.execute(select(Request).where(Request.id == _uuid.UUID(request_id)))
    req = result.scalar_one()
    req.status = RequestStatus.AWAITING_INFO
    await db_session.flush()

    resp = await anon_client.post(
        f"/api/requests/{request_id}/respond",
        json={"body": "Here is the additional information you requested."},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "InfoReceived"


@pytest.mark.asyncio
async def test_respond_wrong_status_rejected(anon_client: AsyncClient, sample_request_payload):
    create = await anon_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]

    resp = await anon_client.post(
        f"/api/requests/{request_id}/respond",
        json={"body": "Some info"},
    )
    assert resp.status_code == 409


# ── PATCH /api/requests/{id} — submitter editing ──────────────────────────────

@pytest.mark.asyncio
async def test_submitter_can_edit_own_request(
    authed_client: AsyncClient, sample_request_payload
):
    """The submitter may edit the title, severity, etc. while the request is
    still under review."""
    create = await authed_client.post("/api/requests", json=sample_request_payload)
    assert create.status_code == 201
    request_id = create.json()["id"]

    resp = await authed_client.patch(
        f"/api/requests/{request_id}",
        json={"title": "Updated title", "severity": "High"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated title"
    assert body["severity"] == "High"
    # Untouched fields stay the same
    assert body["pod"] == sample_request_payload["pod"]


@pytest.mark.asyncio
async def test_edit_with_no_changes_is_idempotent(
    authed_client: AsyncClient, sample_request_payload
):
    create = await authed_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]

    resp = await authed_client.patch(f"/api/requests/{request_id}", json={})
    assert resp.status_code == 200
    assert resp.json()["title"] == sample_request_payload["title"]


@pytest.mark.asyncio
async def test_non_submitter_requestor_cannot_edit(
    authed_client: AsyncClient,
    anon_client: AsyncClient,
    sample_request_payload,
    db_session,
):
    """A different user (not the submitter, no privileged role) gets 403."""
    import uuid as _uuid
    from sqlalchemy import select
    from app.models.request import Request

    create = await anon_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]

    # Reassign to a different submitter so authed_client (oid=test-oid-1234) is NOT the owner
    result = await db_session.execute(select(Request).where(Request.id == _uuid.UUID(request_id)))
    req = result.scalar_one()
    req.submitter_oid = "someone-else"
    await db_session.flush()
    await db_session.commit()

    resp = await authed_client.patch(
        f"/api/requests/{request_id}", json={"title": "Sneaky edit"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_pm_can_edit_any_request(
    pm_client: AsyncClient,
    anon_client: AsyncClient,
    sample_request_payload,
):
    """A Product Manager may edit any request, regardless of who submitted it."""
    create = await anon_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]

    resp = await pm_client.patch(
        f"/api/requests/{request_id}",
        json={"severity": "Critical"},
    )
    assert resp.status_code == 200
    assert resp.json()["severity"] == "Critical"


@pytest.mark.asyncio
async def test_cannot_edit_after_approval(
    authed_client: AsyncClient,
    sample_request_payload,
    db_session,
):
    """Once approved, the request is no longer editable — returns 409."""
    import uuid as _uuid
    from sqlalchemy import select
    from app.models.request import Request, RequestStatus

    create = await authed_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]

    result = await db_session.execute(select(Request).where(Request.id == _uuid.UUID(request_id)))
    req = result.scalar_one()
    req.status = RequestStatus.APPROVED
    await db_session.flush()
    await db_session.commit()

    resp = await authed_client.patch(
        f"/api/requests/{request_id}", json={"title": "Too late"}
    )
    assert resp.status_code == 409
    assert "no longer editable" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_edit_unauthenticated_rejected(
    anon_client: AsyncClient, sample_request_payload
):
    create = await anon_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]

    resp = await anon_client.patch(
        f"/api/requests/{request_id}", json={"title": "no auth"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_edit_writes_audit_log(
    authed_client: AsyncClient, sample_request_payload, db_session
):
    """Each changed field should produce an audit log entry, so reviewers can
    see what the submitter modified after the request was first opened.
    """
    import uuid as _uuid
    from sqlalchemy import select
    from app.models.request import AuditLog

    create = await authed_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]

    await authed_client.patch(
        f"/api/requests/{request_id}",
        json={"title": "New title", "severity": "Critical"},
    )

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.request_id == _uuid.UUID(request_id))
    )
    actions = [log.action for log in result.scalars().all()]
    assert "edit:title" in actions
    assert "edit:severity" in actions


@pytest.mark.asyncio
async def test_edit_fires_jsm_activity_comment(
    authed_client: AsyncClient,
    sample_request_payload,
    jsm_task_spies,
):
    create = await authed_client.post("/api/requests", json=sample_request_payload)
    request_id = create.json()["id"]
    jsm_task_spies["comment"].reset_mock()

    await authed_client.patch(
        f"/api/requests/{request_id}", json={"title": "Refined title"}
    )

    jsm_task_spies["comment"].assert_called_once()
    args = jsm_task_spies["comment"].call_args[0]
    assert args[0] == request_id
    assert "edited" in args[1].lower()
    assert "title" in args[1]


# IMPROVEMENT: PM dashboard filtering - don't show own requests

@pytest.mark.asyncio
async def test_pm_dashboard_excludes_own_requests(
    pm_client: AsyncClient,
    anon_client: AsyncClient,
    sample_request_payload,
    db_session,
):
    """PM should not see their own requests on dashboard (they use My Requests tab)"""
    import uuid as _uuid
    from sqlalchemy import select
    from app.models.request import Request

    # PM creates a request
    create = await pm_client.post("/api/requests", json=sample_request_payload)
    assert create.status_code == 201
    pm_request_id = create.json()["id"]

    # Anonymous user creates a request (for comparison)
    create2 = await anon_client.post("/api/requests", json=sample_request_payload)
    assert create2.status_code == 201
    other_request_id = create2.json()["id"]

    # PM queries dashboard - should NOT see their own request
    resp = await pm_client.get("/api/requests")
    assert resp.status_code == 200
    data = resp.json()

    # PM's own request should NOT be in the results
    pm_ids = [item["id"] for item in data["items"]]
    assert pm_request_id not in pm_ids, "PM should not see their own request"

    # But should see other requests if they exist
    # (this depends on whether other_request_id is in the results)
    # The key is that pm_request_id is definitely not there


@pytest.mark.asyncio
async def test_pod_reviewer_sees_all_pm_requests(
    reviewer_client: AsyncClient,
    pm_client: AsyncClient,
    sample_request_payload,
):
    """Pod reviewers should see all requests, including PM's own requests"""
    # PM creates a request
    create = await pm_client.post("/api/requests", json=sample_request_payload)
    assert create.status_code == 201
    request_id = create.json()["id"]

    # Reviewer queries dashboard - should see PM's request
    resp = await reviewer_client.get("/api/requests")
    assert resp.status_code == 200
    data = resp.json()

    # Should find PM's request
    found = any(item["id"] == request_id for item in data["items"])
    assert found, "Reviewer should see PM's request"


@pytest.mark.asyncio
async def test_pm_export_excludes_own_requests(
    pm_client: AsyncClient,
    sample_request_payload,
):
    """PM's CSV export should not include their own requests"""
    # PM creates a request
    create = await pm_client.post("/api/requests", json=sample_request_payload)
    assert create.status_code == 201
    request_title = create.json()["title"]

    # PM exports CSV - should not include their own request
    resp = await pm_client.get("/api/requests/export")
    assert resp.status_code == 200
    csv_content = resp.text

    # Request title should not appear in CSV export
    assert request_title not in csv_content, "PM's own request should not be in export"
