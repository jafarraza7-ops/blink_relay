"""
api/requests.py — CRUD endpoints for Blink Relay intake requests.

Endpoints:
  POST   /requests              — Submit a new Feature/Defect request (any auth'd user).
  GET    /requests              — List all requests with filters (PodReviewer/PM only).
  GET    /requests/export       — Export filtered requests as CSV (PodReviewer/PM only).
  GET    /requests/mine         — Submitter's own request history.
  GET    /requests/{id}         — Single request detail (no role restriction).
  PATCH  /requests/{id}         — Edit a request while still under review.
  POST   /requests/{id}/respond — Public endpoint: submitter replies to a clarification question.

Key behaviours:
  - On creation, a JSM ticket and submission email are triggered immediately (Celery tasks).
  - If pod == UNKNOWN at submission, an AI-based routing task tries to assign the correct pod.
  - Commits are done before .delay() calls because eager-mode Celery tasks hit the same DB row.
  - region is always stored as a JSON array; the field validator prevents an empty list.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

logger = logging.getLogger(__name__)

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import Role, UserClaims, get_current_user, get_optional_user, require_role, is_same_user
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
    TimelineEventResponse,
)
from app.workers.tasks import (
    route_request_to_pod,
    task_create_jsm_ticket,
    task_jsm_add_comment,
    task_notify_pm_clarification_response,
    task_send_status_notification,
)
from app.workers.email_tasks import (
    task_send_request_creation_email,
    task_send_status_update_email,
    task_send_new_message_email,
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


def _build_request_filters(filters: dict, user: UserClaims, exclude_pm_requests: bool = False) -> list:
    """Build SQLAlchemy filter list for request queries.

    Consolidates PM-exclusion and pod/status filtering logic across endpoints.
    When exclude_pm_requests=True and user is ProductManager, filters out requests
    where the submitter matches the current user (prevents PMs from seeing their own requests).
    Supports both OID-based (Azure AD) and email-based authentication.

    Args:
        filters: Dictionary containing optional filter keys: pod, status, type, priority, search
        user: Current user claims with roles, oid, and email
        exclude_pm_requests: If True, PMs don't see their own submitted requests

    Returns:
        List of SQLAlchemy filter conditions ready to pass to .where()
    """
    conditions = []

    # PM dashboard filtering: exclude own requests
    if exclude_pm_requests and "ProductManager" in user.roles:
        if user.oid:
            conditions.append(Request.submitter_oid != user.oid)
        else:
            conditions.append(Request.submitter_email != user.email)

    # Pod filtering
    if filters.get("pod"):
        conditions.append(Request.pod == filters["pod"])

    # Status filtering
    if filters.get("status"):
        conditions.append(Request.status == filters["status"])

    # Type filtering
    if filters.get("type"):
        conditions.append(Request.request_type == filters["type"])

    # Priority filtering
    if filters.get("priority"):
        conditions.append(Request.priority == filters["priority"])

    # Search/title filtering
    if filters.get("search"):
        conditions.append(Request.title.ilike(f"%{filters['search']}%"))

    return conditions


async def _queue_creation_tasks(req: Request, settings, logger) -> None:
    """Queue background tasks after request creation (JSM, Jira, notifications).

    Each task is queued independently with its own error handling so that
    failure to queue one task doesn't prevent queuing others.
    Logs warnings for failures but never raises — task queuing is best-effort.

    Args:
        req: The newly created Request model instance
        settings: Application settings (for FRONTEND_URL)
        logger: Logger instance for warnings on failure
    """
    # JSM ticket creation
    try:
        task_create_jsm_ticket.delay(str(req.id))
    except Exception:
        _log_task_error("task_create_jsm_ticket", str(req.id), logger)

    # NOTE: We do NOT send task_send_status_notification on creation.
    # That task is reserved for status changes (approve/reject/update).
    # The request creation email already notifies the submitter.

    # Creation email with confirmation link
    try:
        request_url = f"{settings.FRONTEND_URL}/requests/{req.id}"
        task_send_request_creation_email.delay(
            req.submitter_email,
            req.reference_id,
            req.title,
            req.request_type.value,
            req.priority.value,
            req.submitter_name,
            request_url,
        )
    except Exception:
        _log_task_error("task_send_request_creation_email", str(req.id), logger)

    # AI-based pod routing (only if submitter couldn't identify pod)
    if req.pod == Pod.UNKNOWN:
        try:
            route_request_to_pod.delay(str(req.id))
        except Exception:
            _log_task_error("route_request_to_pod", str(req.id), logger)


def _log_task_error(task_name: str, req_id: str, logger) -> None:
    """Log a task queueing failure with consistent formatting and detail level.

    Used across all endpoints when Celery task.delay() fails. Logs at warning
    level with exception info for debugging, but is non-fatal since task
    queueing is best-effort.

    Args:
        task_name: Name of the Celery task that failed to queue
        req_id: Request ID for context
        logger: Logger instance to write to
    """
    logger.warning(
        f"Failed to queue {task_name} for request {req_id} — task may be retried later",
        exc_info=True
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class RequestCreate(BaseModel):
    """Request creation payload with validation for required fields.

    Required fields (title, business_problem, affected_area) are validated
    to ensure they contain non-whitespace content. Optional fields are only
    validated if provided by the user.
    """
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

    @field_validator('title', 'business_problem', 'affected_area', mode='before')
    @classmethod
    def validate_required_not_empty(cls, v: str) -> str:
        """Validate that required fields are not empty or whitespace-only.

        Strips leading/trailing whitespace and rejects if field becomes empty.
        Prevents users from submitting requests with only spaces in required fields.

        Args:
            v: Input string value from the request payload

        Returns:
            Stripped string value

        Raises:
            ValueError: If the field is empty or contains only whitespace
        """
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError('This field cannot be empty or contain only spaces')
            return stripped
        return v

    @field_validator('expected_outcome', 'steps_to_reproduce', 'additional_context', mode='before')
    @classmethod
    def validate_optional_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate optional fields: if provided, must not be whitespace-only.

        If user provides an optional field, it must contain meaningful content.
        Empty strings (field not provided) are allowed.

        Args:
            v: Input string value from the request payload

        Returns:
            Stripped string value or None

        Raises:
            ValueError: If the field contains only whitespace
        """
        if isinstance(v, str) and v:  # Only validate if non-empty string
            stripped = v.strip()
            if not stripped:
                raise ValueError('This field cannot contain only spaces')
            return stripped
        return v

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

    When fields are provided, they must not be empty or whitespace-only,
    following the same validation rules as RequestCreate.
    """
    title: Optional[str] = None
    priority: Optional[Priority] = None
    region: Optional[list[Region]] = None
    business_problem: Optional[str] = None
    expected_outcome: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    affected_area: Optional[str] = None
    additional_context: Optional[str] = None

    @field_validator('title', 'business_problem', 'affected_area', mode='before')
    @classmethod
    def validate_required_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate that fields are not whitespace-only when provided.

        When a required field is included in an update, it must contain
        meaningful content (cannot be only spaces). Null/missing fields are allowed.

        Args:
            v: Input string value from the request payload

        Returns:
            Stripped string value or None

        Raises:
            ValueError: If the field contains only whitespace
        """
        if isinstance(v, str) and v:
            stripped = v.strip()
            if not stripped:
                raise ValueError('This field cannot be empty or contain only spaces')
            return stripped
        return v

    @field_validator('expected_outcome', 'steps_to_reproduce', 'additional_context', mode='before')
    @classmethod
    def validate_optional_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate optional fields: if provided, must not be whitespace-only.

        Args:
            v: Input string value from the request payload

        Returns:
            Stripped string value or None

        Raises:
            ValueError: If the field contains only whitespace
        """
        if isinstance(v, str) and v:
            stripped = v.strip()
            if not stripped:
                raise ValueError('This field cannot contain only spaces')
            return stripped
        return v

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


class SimilarRequestResponse(BaseModel):
    id: str
    reference_id: str
    title: str
    pod: Pod
    status: RequestStatus
    similarity_score: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/requests", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: RequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[UserClaims], Depends(get_optional_user)],
) -> RequestResponse:
    """Submit a new intake request.

    Uses get_optional_user so unauthenticated (external) submissions are still
    accepted — the submitter fields fall back to anonymous identifiers in that case.
    """
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

    settings = get_settings()
    await _queue_creation_tasks(req, settings, logger)

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
    """Paginated list of all requests for the reviewer dashboard.
    Supports filtering by pod, status, type, priority, and title keyword search.

    Both PMs and PodReviewers see all requests in the dashboard.
    PMs can also access their own submitted requests here, in addition to 'My Requests' tab.
    """
    filter_params = {
        "pod": pod,
        "status": status_filter,
        "type": request_type,
        "priority": priority,
        "search": search,
    }
    filters = _build_request_filters(filter_params, user, exclude_pm_requests=False)

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


@router.get("/requests/export")
async def export_requests_csv(
    user: Annotated[UserClaims, Depends(require_role(Role.POD_REVIEWER, Role.PRODUCT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db)],
    pod: Optional[Pod] = Query(None),
    status_filter: Optional[RequestStatus] = Query(None, alias="status"),
    request_type: Optional[RequestType] = Query(None),
    priority: Optional[Priority] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
) -> StreamingResponse:
    """Export all matching requests as a CSV file (no pagination limit).

    Includes all requests visible to the user in the dashboard — both PMs and PodReviewers
    see the complete dataset they have access to, including their own submitted requests.
    """
    filter_params = {
        "pod": pod,
        "status": status_filter,
        "type": request_type,
        "priority": priority,
        "search": search,
    }
    filters = _build_request_filters(filter_params, user, exclude_pm_requests=False)

    result = await db.execute(
        select(Request).where(*filters).order_by(Request.created_at.desc())
    )
    items = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reference ID", "Title", "Type", "Status", "Pod", "Priority", "Region",
        "Submitter Name", "Submitter Email", "Affected Area",
        "Jira Ticket", "JSM Ticket", "Created At", "Updated At",
    ])
    for r in items:
        region = ", ".join(r.region) if isinstance(r.region, list) else str(r.region)
        writer.writerow([
            r.reference_id or "",
            r.title,
            str(r.request_type),
            str(r.status),
            str(r.pod),
            str(r.priority),
            region,
            r.submitter_name,
            r.submitter_email,
            r.affected_area,
            r.jira_ticket_key or "",
            r.jsm_ticket_key or "",
            r.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            r.updated_at.strftime("%Y-%m-%d %H:%M UTC"),
        ])

    output.seek(0)
    filename = f"blink-requests-{datetime.now(tz=timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    """Return the authenticated user's own submitted requests.

    IMPROVEMENT: Support both Azure AD and email-based authentication
    - Azure AD users: identified by submitter_oid (stable Entra ID identifier)
    - Email users: identified by submitter_email (no OID available)

    This ensures users only see requests they created, regardless of auth method.
    Fixes issue where email users saw all email-authenticated requests.
    """
    # Build submitter filter using both OID and email for backward compatibility
    # (handles users who authenticated via either method).
    submitter_filters = []
    if user.oid:
        submitter_filters.append(Request.submitter_oid == user.oid)
    submitter_filters.append(Request.submitter_email == user.email)
    submitter_filter = or_(*submitter_filters) if len(submitter_filters) > 1 else submitter_filters[0]

    filters = [submitter_filter]
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
    """Fetch a single request by ID. No role restriction — used by both the
    reviewer dashboard and the requestor's own detail view."""
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return RequestResponse.model_validate(req)


@router.get("/requests/{request_id}/similar", response_model=list[SimilarRequestResponse])
async def get_similar_requests(
    request_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> list[SimilarRequestResponse]:
    """Find requests similar to the given request by keyword matching.

    Returns up to `limit` similar requests from the same pod/type,
    ranked by Jaccard similarity score (0-100).
    """
    from app.services.similarity_service import find_similar_requests

    similar = await find_similar_requests(db, str(request_id), limit=limit)
    return [SimilarRequestResponse(**s.__dict__) for s in similar]


@router.get("/requests/{request_id}/timeline", response_model=list[TimelineEventResponse])
async def get_request_timeline(
    request_id: uuid.UUID,
    user: Annotated[UserClaims, Depends(get_optional_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TimelineEventResponse]:
    """Get the complete lifecycle timeline for a request.

    Returns all status changes, approvals, rejections, and clarifications
    in chronological order with actor information and timestamps.
    Includes initial submission as first event.

    The timeline is constructed from:
      1. Initial submission event (created_at, submitter info)
      2. All audit log entries ordered chronologically

    Requestors see their own request timeline; PMs see all timelines.
    """
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # Query audit logs ordered by created_at ascending
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.request_id == request_id)
        .order_by(AuditLog.created_at.asc())
    )
    logs = result.scalars().all()

    events: list[TimelineEventResponse] = []

    # Add initial submission event
    events.append(TimelineEventResponse(
        timestamp=req.created_at,
        action="submitted",
        actor_name=req.submitter_name,
        actor_email=req.submitter_email,
        details=f"Request submitted with title: {req.title}",
        status=req.status if not logs else None,  # Only show status if no transitions yet
    ))

    # Add audit log events
    for log in logs:
        # Only show meaningful status-change-related events
        if log.action in ["status_change", "approved", "rejected", "info_provided", "request_cancelled"]:
            action_label = log.action.replace("_", " ").title()
            details = f"{action_label}: {log.previous_value} → {log.new_value}"
            events.append(TimelineEventResponse(
                timestamp=log.created_at,
                action=log.action,
                actor_name=log.actor_oid if not log.actor_oid or log.actor_oid == "external" else log.actor_oid,
                actor_email=log.actor_email,
                details=details,
                status=log.new_value,
            ))

    return events


@router.post("/requests/{request_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_request(
    request_id: uuid.UUID,
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Cancel a request. Only the original requestor can cancel their own request.
    Cancellation is only allowed for Submitted, InReview, and AwaitingInfo statuses."""
    from app.models.request import ALLOWED_TRANSITIONS, AuditLog, Message, MessageType

    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # Only the requestor can cancel their own request (or admins)
    is_admin = user.roles and Role.ADMIN in user.roles
    if not is_admin:
        # Use is_same_user to check both OID and email auth methods
        is_requestor = is_same_user(user, req.submitter_oid, req.submitter_email)

        if not is_requestor:
            raise HTTPException(status_code=403, detail="Only the requestor can cancel this request")

    # Validate status transition
    if RequestStatus.CANCELLED not in ALLOWED_TRANSITIONS.get(req.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel request with status '{req.status}'"
        )

    prev_status = req.status
    req.status = RequestStatus.CANCELLED
    await db.flush()

    # Add audit log
    db.add(AuditLog(
        request_id=req.id,
        actor_oid=user.oid,
        actor_email=user.email,
        action="request_cancelled",
        previous_value=str(prev_status),
        new_value=str(RequestStatus.CANCELLED),
    ))

    # Add status change message
    db.add(Message(
        request_id=req.id,
        author_oid=user.oid,
        author_email=user.email,
        author_name=user.name,
        body=f"Request cancelled by {user.name}.",
        is_internal=False,
        message_type=MessageType.STATUS_CHANGE,
    ))

    await db.commit()

    # Send cancellation notification email
    try:
        from app.workers.email_tasks import task_send_request_cancellation_email
        cancellation_date = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")
        task_send_request_cancellation_email.delay(
            req.submitter_email,
            req.reference_id,
            req.title,
            user.name,
            cancellation_date,
        )
    except Exception:
        _log_task_error("task_send_request_cancellation_email", str(req.id), logger)

    # Add comment to JSM
    try:
        from app.workers.tasks import task_jsm_add_comment
        task_jsm_add_comment.delay(str(req.id), f"Request cancelled by {user.name}.", False)
    except Exception:
        _log_task_error("task_jsm_add_comment", str(req.id), logger)

    return {"id": str(req.id), "status": req.status.value}


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

    # Send email if status was changed
    if "status" in changed_summary:
        try:
            settings = get_settings()
            old_status = changes.get("status")  # The new status is already in req
            task_send_status_update_email.delay(
                req.submitter_email,
                req.reference_id,
                req.title,
                str(changes["status"]),  # old_value before setattr
                req.status.value,
                req.submitter_name,
                f"{settings.FRONTEND_URL}/requests/{req.id}",
            )
        except Exception:
            _log_task_error("task_send_status_update_email", str(req.id), logger)

    # Notify JSM so the requestor's service-desk ticket reflects the edit.
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
