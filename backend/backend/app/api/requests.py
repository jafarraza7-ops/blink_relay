from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role, UserClaims, get_current_user, get_optional_user, require_role
from app.models.request import (
    AuditLog,
    Message,
    MessageType,
    Pod,
    Region,
    Request,
    RequestStatus,
    Priority,
    RequestType,
)
from app.workers.tasks import (
    route_request_to_pod,
    task_create_jsm_ticket,
    task_jsm_add_comment,
    task_notify_pm_clarification_response,
    task_send_status_notification,
)

router = APIRouter(tags=["requests"])


async def _ensure_reference_id(req: Request, db: AsyncSession) -> None:
    """Generate BLR-YYYY-NNNN reference_id when the DB trigger hasn't set one (SQLite)."""
    if req.reference_id:
        return
    year = datetime.now(tz=timezone.utc).strftime("%Y")
    prefix = f"BLR-{year}-"
    result = await db.execute(
        select(func.count()).where(Request.reference_id.like(f"{prefix}%"))
    )
    count = result.scalar_one() or 0
    req.reference_id = f"{prefix}{(count + 1):04d}"


# ── Schemas ───────────────────────────────────────────────────────────────────

class RequestCreate(BaseModel):
    title: str
    request_type: RequestType
    pod: Pod
    region: list[Region] = Field(default_factory=lambda: [Region.NA])
    priority: Priority = Priority.MEDIUM
    business_problem: str
    expected_outcome: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    affected_area: str
    additional_context: Optional[str] = None

    @field_validator('region')
    @classmethod
    def region_not_empty(cls, v: list[Region]) -> list[Region]:
        if not v:
            raise ValueError('At least one region must be selected')
        return v


class RespondPayload(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    responder_name: Optional[str] = None
    responder_email: Optional[str] = None


class RequestUpdate(BaseModel):
    """Partial update — only the submitter (or PM/Admin) may edit, and only
    while the request is still under review (statuses listed in
    ``EDITABLE_STATUSES`` below). All fields are optional; unset fields are
    left unchanged.
    """
    title: Optional[str] = None
    priority: Optional[Priority] = None
    region: Optional[list[Region]] = None
    business_problem: Optional[str] = None
    expected_outcome: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    affected_area: Optional[str] = None
    additional_context: Optional[str] = None

    @field_validator('region')
    @classmethod
    def region_not_empty(cls, v: Optional[list[Region]]) -> Optional[list[Region]]:
        if v is not None and not v:
            raise ValueError('At least one region must be selected')
        return v


# Statuses where the submitter is still allowed to edit. After approve/reject
# the request becomes read-only — further changes go through the dev ticket.
EDITABLE_STATUSES: set[RequestStatus] = {
    RequestStatus.SUBMITTED,
    RequestStatus.IN_REVIEW,
    RequestStatus.AWAITING_INFO,
    RequestStatus.INFO_RECEIVED,
}


class RequestResponse(BaseModel):
    id: uuid.UUID
    reference_id: Optional[str]
    title: str
    request_type: RequestType
    pod: Pod
    region: list[str]
    priority: Priority
    status: RequestStatus
    business_problem: str
    expected_outcome: Optional[str]
    steps_to_reproduce: Optional[str]
    affected_area: str
    additional_context: Optional[str]
    submitter_email: str
    submitter_name: str
    jira_ticket_key: Optional[str]
    jira_ticket_url: Optional[str]
    jsm_ticket_key: Optional[str]
    jsm_ticket_url: Optional[str]
    jsm_resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequestListResponse(BaseModel):
    items: list[RequestResponse]
    total: int
    page: int
    page_size: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/requests", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: RequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[UserClaims], Depends(get_optional_user)],
) -> RequestResponse:
    submitter_oid = user.oid if user else "anonymous"
    submitter_email = user.email if user else "unknown@external"
    submitter_name = user.name if user else "External User"

    req = Request(
        **payload.model_dump(),
        submitter_oid=submitter_oid,
        submitter_email=submitter_email,
        submitter_name=submitter_name,
    )
    db.add(req)
    await db.flush()
    await _ensure_reference_id(req, db)
    await db.commit()  # commit before eager tasks read the same DB

    try:
        task_create_jsm_ticket.delay(str(req.id))
    except Exception:
        logger.warning("task_create_jsm_ticket raised in eager mode — non-fatal", exc_info=True)
    try:
        task_send_status_notification.delay(str(req.id))
    except Exception:
        logger.warning("task_send_status_notification raised in eager mode — non-fatal", exc_info=True)
    if req.pod == Pod.UNKNOWN:
        try:
            route_request_to_pod.delay(str(req.id))
        except Exception:
            logger.warning("route_request_to_pod raised in eager mode — non-fatal", exc_info=True)

    return RequestResponse.model_validate(req)


@router.get("/requests", response_model=RequestListResponse)
async def list_requests(
    user: Annotated[UserClaims, Depends(require_role(Role.POD_REVIEWER, Role.PRODUCT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db)],
    pod: Optional[Pod] = Query(None),
    status_filter: Optional[RequestStatus] = Query(None, alias="status"),
    request_type: Optional[RequestType] = Query(None),
    priority: Optional[Priority] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=1000),
) -> RequestListResponse:
    filters = []
    if pod:
        filters.append(Request.pod == pod)
    if status_filter:
        filters.append(Request.status == status_filter)
    if request_type:
        filters.append(Request.request_type == request_type)
    if priority:
        filters.append(Request.priority == priority)
    if search:
        filters.append(Request.title.ilike(f"%{search}%"))

    count_result = await db.execute(select(func.count()).select_from(Request).where(*filters))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Request).where(*filters).order_by(Request.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()

    return RequestListResponse(
        items=[RequestResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/requests/mine", response_model=RequestListResponse)
async def list_my_requests(
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Optional[RequestStatus] = Query(None, alias="status"),
    request_type: Optional[RequestType] = Query(None),
    priority: Optional[Priority] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=1000),
) -> RequestListResponse:
    """Return the authenticated user's own submitted requests."""
    filters = [Request.submitter_oid == user.oid]
    if status_filter:
        filters.append(Request.status == status_filter)
    if request_type:
        filters.append(Request.request_type == request_type)
    if priority:
        filters.append(Request.priority == priority)
    if search:
        filters.append(Request.title.ilike(f"%{search}%"))

    count_result = await db.execute(select(func.count()).select_from(Request).where(*filters))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Request).where(*filters).order_by(Request.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()

    return RequestListResponse(
        items=[RequestResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/requests/{request_id}", response_model=RequestResponse)
async def get_request(
    request_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestResponse:
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return RequestResponse.model_validate(req)


@router.patch("/requests/{request_id}", response_model=RequestResponse)
async def update_request(
    request_id: uuid.UUID,
    payload: RequestUpdate,
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestResponse:
    """Allow the submitter (or PM/Admin) to edit a request while it is still
    under review.

    Notes
    -----
    * ``request_type`` and ``pod`` are intentionally not editable — changing
      either implies re-routing and re-triage, which should be a workflow
      action by a reviewer, not an inline edit.
    * Only fields explicitly set in the payload are written; unset fields
      stay at their current value.
    """
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    is_submitter = req.submitter_oid == user.oid
    is_privileged = any(r in user.roles for r in (Role.PRODUCT_MANAGER, Role.ADMIN))
    if not (is_submitter or is_privileged):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the submitter or a product manager can edit this request",
        )

    if req.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request in status '{req.status}' is no longer editable",
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        # Nothing to update — return the current state idempotently.
        return RequestResponse.model_validate(req)

    changed_summary: list[str] = []
    for field, new_value in changes.items():
        old_value = getattr(req, field)
        if old_value != new_value:
            setattr(req, field, new_value)
            db.add(AuditLog(
                request_id=req.id,
                actor_oid=user.oid,
                actor_email=user.email,
                action=f"edit:{field}",
                previous_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
            ))
            changed_summary.append(field)

    await db.commit()
    await db.refresh(req)

    if changed_summary:
        task_jsm_add_comment.delay(
            str(req.id),
            f"Request edited by {user.name} — fields updated: {', '.join(changed_summary)}",
            True,
        )

    return RequestResponse.model_validate(req)


@router.post("/requests/{request_id}/respond", status_code=status.HTTP_201_CREATED)
async def respond_to_request(
    request_id: uuid.UUID,
    payload: RespondPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Public endpoint — submitters provide additional information requested by reviewers."""
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != RequestStatus.AWAITING_INFO:
        raise HTTPException(
            status_code=409,
            detail=f"Request is in status '{req.status}', not AwaitingInfo",
        )

    author_oid = "external"
    author_email = payload.responder_email or req.submitter_email
    author_name = payload.responder_name or req.submitter_name

    db.add(Message(
        request_id=request_id,
        author_oid=author_oid,
        author_email=author_email,
        author_name=author_name,
        body=f"Status changed from **Awaiting Info** to **Info Received** — {author_name} submitted additional information.",
        is_internal=False,
        message_type=MessageType.STATUS_CHANGE,
    ))
    msg = Message(
        request_id=request_id,
        author_oid=author_oid,
        author_email=author_email,
        author_name=author_name,
        body=payload.body,
        is_internal=False,
        message_type=MessageType.CLARIFICATION_RESPONSE,
    )
    db.add(msg)

    req.status = RequestStatus.INFO_RECEIVED
    db.add(AuditLog(
        request_id=req.id,
        actor_oid=author_oid,
        actor_email=author_email,
        action="info_provided",
        previous_value=str(RequestStatus.AWAITING_INFO),
        new_value=str(RequestStatus.INFO_RECEIVED),
    ))
    await db.commit()  # commit before eager tasks read the same DB
    task_send_status_notification.delay(str(req.id))
    task_jsm_add_comment.delay(
        str(req.id),
        f"**{author_name}** provided additional information:\n\n{payload.body}",
        True,
    )
    task_notify_pm_clarification_response.delay(str(req.id))

    return {"id": str(req.id), "status": str(req.status), "message": "Response recorded"}
