"""
api/workflow.py — State-transition endpoints for the Blink Relay review workflow.

Endpoints:
  PATCH  /requests/{id}/status  — Generic status move (PodReviewer/PM).
  POST   /requests/{id}/approve — Approve a request and trigger Jira ticket creation (PM only).
  POST   /requests/{id}/reject  — Reject a request with a reason and optional comment (PM only).
  POST   /admin/backfill-jsm    — One-time admin tool to create missing JSM tickets (Admin only).

All transitions are validated against ALLOWED_TRANSITIONS before being applied,
so this router is the single enforcement point for the status state machine.

On every status change:
  - An AuditLog row is written.
  - A Message (status_change type) is added to the request thread.
  - task_send_status_notification is fired to email the requestor.
  - task_jsm_add_comment mirrors the update to the JSM ticket.
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role, UserClaims, require_role
from app.models.request import ALLOWED_TRANSITIONS, AuditLog, Message, MessageType, Request, RequestStatus
from app.workers.tasks import (
    task_close_jsm_ticket,
    task_create_jira_ticket,
    task_create_jsm_ticket,
    task_jira_add_comment,
    task_jsm_add_comment,
    task_send_status_notification,
)

router = APIRouter(tags=["workflow"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    """Payload for a generic status move. Comment is shown in the request thread."""
    status: RequestStatus
    comment: Optional[str] = None


class ApprovePayload(BaseModel):
    """Optional overrides for Jira ticket creation on approval.
    jira_project_override lets the PM direct the ticket to a non-default project.
    epic_title overrides the Jira issue title (defaults to the request title)."""
    jira_project_override: Optional[str] = None
    epic_title: Optional[str] = None


class RejectPayload(BaseModel):
    """reason is a short category string shown in the thread and email;
    comment is an optional free-text elaboration for the requestor."""
    reason: str
    comment: Optional[str] = None


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _get_request_or_404(request_id: uuid.UUID, db: AsyncSession) -> Request:
    """Fetch a Request by UUID or raise 404."""
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


def _add_audit(
    db: AsyncSession,
    req: Request,
    actor: UserClaims,
    action: str,
    prev: str | None = None,
    new: str | None = None,
) -> None:
    """Append an AuditLog entry for the given action. Caller must commit."""
    db.add(AuditLog(
        request_id=req.id,
        actor_oid=actor.oid,
        actor_email=actor.email,
        action=action,
        previous_value=prev,
        new_value=new,
    ))


def _validate_transition(current: RequestStatus, target: RequestStatus) -> None:
    """Raise 409 if the requested status transition is not in ALLOWED_TRANSITIONS."""
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transition from '{current}' to '{target}' is not allowed",
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.patch("/requests/{request_id}/status", response_model=dict)
async def update_status(
    request_id: uuid.UUID,
    payload: StatusUpdate,
    user: Annotated[UserClaims, Depends(require_role(Role.POD_REVIEWER, Role.PRODUCT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Move a request to any valid next status. Used for non-approve/reject transitions
    (e.g. InReview → AwaitingInfo, or InProgress → Completed).

    IMPROVEMENT: Ensure Jira ticket is created regardless of approval method (approve vs status_change).
    This prevents requestors from seeing empty "Dev ticket" column after approval via generic status endpoint.
    """
    req = await _get_request_or_404(request_id, db)
    _validate_transition(req.status, payload.status)
    prev = req.status
    req.status = payload.status
    _add_audit(db, req, user, "status_change", str(prev), str(payload.status))

    msg_body = f"Status changed from **{prev}** to **{payload.status}** by {user.name}."
    if payload.comment:
        msg_body += f"\n\n{payload.comment}"
    db.add(Message(
        request_id=req.id,
        author_oid=user.oid,
        author_email=user.email,
        author_name=user.name,
        body=msg_body,
        is_internal=False,
        message_type=MessageType.STATUS_CHANGE,
    ))
    await db.commit()  # commit before eager task reads the same DB
    try:
        task_send_status_notification.delay(str(req.id))
    except Exception:
        logger.warning("task_send_status_notification raised in eager mode — non-fatal", exc_info=True)

    jsm_msg = f"Status changed: {prev} → {payload.status} by {user.name}"
    if payload.comment:
        jsm_msg += f"\n\nComment: {payload.comment}"
    task_jsm_add_comment.delay(str(req.id), jsm_msg, True)

    # IMPROVEMENT: Create Jira ticket if transitioning to APPROVED
    # This ensures Jira ticket is created regardless of which endpoint approved the request
    if payload.status == RequestStatus.APPROVED and not req.jira_ticket_key:
        try:
            task_create_jira_ticket.delay(str(req.id), None, None, user.name, user.email)
        except Exception:
            logger.warning("task_create_jira_ticket raised in eager mode — non-fatal", exc_info=True)

    return {"id": str(req.id), "status": str(req.status)}


@router.post("/requests/{request_id}/approve", status_code=status.HTTP_200_OK)
async def approve_request(
    request_id: uuid.UUID,
    payload: ApprovePayload,
    user: Annotated[UserClaims, Depends(require_role(Role.PRODUCT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Approve a request and kick off Jira ticket creation.

    Only ProductManagers (or Admins) can approve. After approval the DB is committed
    before firing Celery tasks so the tasks see the updated status and can safely
    read jira_ticket_key once it's populated by task_create_jira_ticket.
    """
    req = await _get_request_or_404(request_id, db)
    _validate_transition(req.status, RequestStatus.APPROVED)

    prev_status = req.status
    req.status = RequestStatus.APPROVED
    _add_audit(db, req, user, "approved", str(prev_status), str(RequestStatus.APPROVED))

    approval_comment = f"Request approved by {user.name}. A Jira implementation ticket will be created shortly."
    db.add(Message(
        request_id=req.id,
        author_oid=user.oid,
        author_email=user.email,
        author_name=user.name,
        body=approval_comment,
        is_internal=False,
        message_type=MessageType.COMMENT,
    ))

    await db.commit()  # commit before eager tasks read the same DB

    try:
        task_create_jira_ticket.delay(str(req.id), payload.jira_project_override, payload.epic_title, user.name, user.email)
    except Exception:
        logger.warning("task_create_jira_ticket raised in eager mode — non-fatal", exc_info=True)
    try:
        task_send_status_notification.delay(str(req.id))
    except Exception:
        logger.warning("task_send_status_notification raised in eager mode — non-fatal", exc_info=True)
    try:
        task_jsm_add_comment.delay(str(req.id), approval_comment, True)
    except Exception:
        logger.warning("task_jsm_add_comment raised in eager mode — non-fatal", exc_info=True)

    return {
        "id": str(req.id),
        "status": str(req.status),
        "message": "Approved — Jira ticket creation queued",
    }


@router.post("/requests/{request_id}/reject", status_code=status.HTTP_200_OK)
async def reject_request(
    request_id: uuid.UUID,
    payload: RejectPayload,
    user: Annotated[UserClaims, Depends(require_role(Role.PRODUCT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Reject a request, recording the reason and notifying the requestor.

    Rejection is terminal — ALLOWED_TRANSITIONS has an empty set for REJECTED.
    The JSM comment is posted before the close attempt so the requestor sees the
    reason even if the ticket-close step fails.
    """
    req = await _get_request_or_404(request_id, db)
    _validate_transition(req.status, RequestStatus.REJECTED)

    prev_status = req.status
    req.status = RequestStatus.REJECTED
    req.rejection_reason = payload.reason
    req.rejection_comment = payload.comment
    req.rejected_by_oid = user.oid
    _add_audit(db, req, user, "rejected", str(prev_status), str(RequestStatus.REJECTED))

    body = f"Request rejected.\n\nReason: {payload.reason}"
    if payload.comment:
        body += f"\n\n{payload.comment}"
    db.add(Message(
        request_id=req.id,
        author_oid=user.oid,
        author_email=user.email,
        author_name=user.name,
        body=body,
        is_internal=False,
        message_type=MessageType.COMMENT,
    ))

    await db.commit()  # commit before eager task reads the same DB
    try:
        task_send_status_notification.delay(str(req.id))
    except Exception:
        logger.warning("task_send_status_notification raised in eager mode — non-fatal", exc_info=True)

    # Post the rejection comment to the JSM ticket first (best-effort),
    # then attempt to close it — separately so a failed close doesn't
    # swallow the comment.
    jsm_comment = f"Request rejected by {user.name}.\n\nReason: {payload.reason}"
    if payload.comment:
        jsm_comment += f"\n\n{payload.comment}"
    try:
        task_jsm_add_comment.delay(str(req.id), jsm_comment, True)
    except Exception:
        logger.warning("task_jsm_add_comment raised in eager mode — non-fatal", exc_info=True)

    try:
        task_close_jsm_ticket.delay(str(req.id), jsm_comment)
    except Exception:
        logger.warning("task_close_jsm_ticket raised in eager mode — non-fatal", exc_info=True)

    try:
        task_jira_add_comment.delay(str(req.id), jsm_comment)
    except Exception:
        logger.warning("task_jira_add_comment raised in eager mode — non-fatal", exc_info=True)

    return {"id": str(req.id), "status": str(req.status)}


@router.post("/admin/backfill-jsm", status_code=status.HTTP_200_OK)
async def backfill_jsm_tickets(
    user: Annotated[UserClaims, Depends(require_role(Role.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Queue JSM ticket creation for every request that doesn't have one yet.

    Idempotent — task_create_jsm_ticket skips requests that already have a
    jsm_ticket_key, so this is safe to call multiple times.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Request).where(Request.jsm_ticket_key.is_(None))
    )
    requests = result.scalars().all()

    if not requests:
        return {"queued": 0, "message": "All requests already have JSM tickets"}

    queued = 0
    for req in requests:
        try:
            task_create_jsm_ticket.delay(str(req.id))
            queued += 1
            logger.info("Queued JSM ticket creation for %s (%s)", req.reference_id or req.id, req.title)
        except Exception:
            logger.warning("Failed to queue JSM task for %s", req.id, exc_info=True)

    return {"queued": queued, "total_missing": len(requests)}
