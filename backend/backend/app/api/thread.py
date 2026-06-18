from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import Role, UserClaims, get_current_user, get_optional_user, require_role, is_same_user
from app.models.request import (
    ALLOWED_TRANSITIONS,
    AuditLog,
    Message,
    MessageType,
    Request,
    RequestStatus,
)
from app.workers.tasks import task_jsm_add_comment, task_jira_add_comment, task_send_clarification_email
from app.workers.email_tasks import task_send_new_message_email

router = APIRouter(tags=["thread"])

_REVIEWER_ROLES = {Role.POD_REVIEWER, Role.PRODUCT_MANAGER, Role.ADMIN}


class MessageCreate(BaseModel):
    """Request to post a message with validation.

    Validates that message body is not empty or whitespace-only before processing.
    Whitespace is automatically stripped during validation.
    """
    body: str
    is_internal: bool = False
    mentions: list[str] = []  # List of mentioned user OIDs

    @field_validator('body', mode='before')
    @classmethod
    def validate_body_not_empty(cls, v):
        """Validate message body is not empty or whitespace-only.

        Users cannot send messages that contain only spaces.
        Whitespace-only messages are rejected before database storage.
        """
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError('Message cannot be empty or contain only spaces')
            return stripped
        return v


class ClarifyPayload(BaseModel):
    """Request to send a clarification question with validation.

    Validates that message body is not empty or whitespace-only before processing.
    """
    body: str

    @field_validator('body', mode='before')
    @classmethod
    def validate_body_not_empty(cls, v):
        """Validate message body is not empty or whitespace-only."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError('Message cannot be empty or contain only spaces')
            return stripped
        return v


class MessageResponse(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    author_email: str
    author_name: str
    body: str
    is_internal: bool
    message_type: str
    mentions: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


def _is_reviewer(user: Optional[UserClaims]) -> bool:
    return user is not None and bool(set(user.roles) & _REVIEWER_ROLES)


@router.get("/requests/{request_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    request_id: uuid.UUID,
    user: Annotated[Optional[UserClaims], Depends(get_optional_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MessageResponse]:
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    q = select(Message).where(Message.request_id == request_id).order_by(Message.created_at)
    if not _is_reviewer(user):
        q = q.where(Message.is_internal == False)  # noqa: E712
    result = await db.execute(q)
    messages = result.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/requests/{request_id}/messages", response_model=MessageResponse, status_code=201)
async def post_message(
    request_id: uuid.UUID,
    payload: MessageCreate,
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Post a message to a request thread.

    Validates that message body is not empty or whitespace-only.
    The body is automatically sanitized (whitespace stripped) before storage.
    """
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # Non-reviewers can only message on their own requests
    if not _is_reviewer(user) and req.submitter_oid != user.oid:
        raise HTTPException(status_code=403, detail="You can only message on your own requests")

    # Non-reviewers cannot post internal notes
    is_internal = payload.is_internal and _is_reviewer(user)

    msg = Message(
        request_id=request_id,
        author_oid=user.oid,
        author_email=user.email,
        author_name=user.name,
        body=payload.body,
        is_internal=is_internal,
        mentions=payload.mentions,
        message_type=MessageType.COMMENT,
    )
    db.add(msg)

    # Audit log message creation
    db.add(AuditLog(
        request_id=request_id,
        actor_oid=user.oid,
        actor_email=user.email,
        action="message_added",
        previous_value=None,
        new_value=payload.body[:200],  # Store preview of message
        event_data={"is_internal": is_internal, "message_type": "comment"},
    ))

    await db.flush()
    await db.refresh(msg)
    await db.commit()

    # Send email notification for new message
    try:
        settings = get_settings()
        # Check if message sender is the requestor
        # Use is_same_user to handle both OID and email auth methods
        is_from_requestor = is_same_user(user, req.submitter_oid, req.submitter_email)

        # IMPROVEMENT: Detect message direction and determine email recipients
        # Handles both Azure AD users (OID-based) and email users (email-based)
        message_preview = payload.body[:100].replace("\n", " ")

        if not is_from_requestor:  # Message from reviewer/PM to requestor
            # IMPROVEMENT: Skip self-email when PM is also the requestor
            # Scenario: PM creates request, another PM replies → email sent
            #         PM creates request, PM replies → skip self-email
            if user.email != req.submitter_email:
                logger.info(f"📧 Queuing email to requestor {req.submitter_email} from {user.email}")
                task_send_new_message_email.delay(
                    req.submitter_email,
                    req.reference_id,
                    req.title,
                    user.name,
                    message_preview,
                    req.submitter_name,
                    f"{settings.FRONTEND_URL}/requests/{req.id}",
                )
            else:
                logger.info(f"ℹ️ Skipping self-email: {user.email} is both reviewer and requestor")
        else:  # Message from requestor to reviewers - notify all PMs/reviewers
            # FEATURE: Notify all PM/Admin/PodReviewers about requestor messages
            # Each reviewer gets their own email notification
            from app.models.request import User

            logger.info(f"📧 Queuing email to PMs from requestor {user.email}")
            # Get all users and filter for review roles
            result = await db.execute(select(User))
            all_users = result.scalars().all()

            reviewer_roles = {Role.PRODUCT_MANAGER, Role.ADMIN, Role.POD_REVIEWER}
            for reviewer in all_users:
                # Send email to all reviewers except the requestor (self-exclusion)
                if reviewer.email and reviewer.email != user.email:
                    reviewer_role_set = set(reviewer.roles) if reviewer.roles else set()
                    if reviewer_role_set & reviewer_roles:  # Intersection check - has at least one reviewer role
                        logger.info(f"📧 Queuing email to reviewer {reviewer.email}")
                        task_send_new_message_email.delay(
                            reviewer.email,
                            req.reference_id,
                            req.title,
                            user.name,
                            message_preview,
                            req.submitter_name,
                            f"{settings.FRONTEND_URL}/requests/{req.id}",
                        )
    except Exception as e:
        logger.exception(f"Failed to queue email: {e}")

    jsm_body = f"**{user.name}** ({user.email}):\n\n{payload.body}"
    task_jsm_add_comment.delay(str(request_id), jsm_body, not is_internal)

    # Sync message to JIRA ticket if it exists
    if req.jira_ticket_key:
        task_jira_add_comment.delay(str(request_id), jsm_body)

    # Notify mentioned users if any
    if payload.mentions:
        from app.services.mention_service import notify_mentioned_users
        await notify_mentioned_users(
            request_id=request_id,
            message_id=msg.id,
            mentioned_oids=payload.mentions,
            author_name=user.name,
            body_preview=payload.body[:100],
            db=db,
        )

    return MessageResponse.model_validate(msg)


@router.post("/requests/{request_id}/clarify", response_model=MessageResponse, status_code=201)
async def send_clarification(
    request_id: uuid.UUID,
    payload: ClarifyPayload,
    user: Annotated[UserClaims, Depends(require_role(Role.PRODUCT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """PM sends a clarification question. Sets status to AwaitingInfo and emails the requestor."""
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    allowed_from = {
        RequestStatus.IN_REVIEW,
        RequestStatus.AWAITING_INFO,
        RequestStatus.INFO_RECEIVED,
        RequestStatus.SUBMITTED,
    }
    if req.status not in allowed_from:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot request clarification from status '{req.status}'",
        )

    prev_status = req.status
    req.status = RequestStatus.AWAITING_INFO

    # Only log a status change if the status actually changed
    if prev_status != RequestStatus.AWAITING_INFO:
        db.add(Message(
            request_id=request_id,
            author_oid=user.oid,
            author_email=user.email,
            author_name=user.name,
            body=f"Status changed from **{prev_status}** to **Awaiting Info** by {user.name}.",
            is_internal=False,
            message_type=MessageType.STATUS_CHANGE,
        ))
        db.add(AuditLog(
            request_id=req.id,
            actor_oid=user.oid,
            actor_email=user.email,
            action="clarification_requested",
            previous_value=str(prev_status),
            new_value=str(RequestStatus.AWAITING_INFO),
        ))

    # Clarification message
    msg = Message(
        request_id=request_id,
        author_oid=user.oid,
        author_email=user.email,
        author_name=user.name,
        body=payload.body,
        is_internal=False,
        message_type=MessageType.CLARIFICATION_QUESTION,
    )
    db.add(msg)

    # Audit log for clarification message
    db.add(AuditLog(
        request_id=req.id,
        actor_oid=user.oid,
        actor_email=user.email,
        action="clarification_sent",
        previous_value=None,
        new_value=payload.body[:200],
        event_data={"message_type": "clarification_question"},
    ))
    await db.flush()
    await db.refresh(msg)
    await db.commit()

    task_send_clarification_email.delay(str(request_id), payload.body)
    clarify_body = f"**{user.name}** ({user.email}) requested clarification:\n\n{payload.body}"
    task_jsm_add_comment.delay(str(request_id), clarify_body, True)

    # Sync clarification to JIRA ticket if it exists
    if req.jira_ticket_key:
        task_jira_add_comment.delay(str(request_id), clarify_body)

    return MessageResponse.model_validate(msg)
