from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role, UserClaims, get_current_user, get_optional_user, require_role
from app.models.request import (
    ALLOWED_TRANSITIONS,
    AuditLog,
    Message,
    MessageType,
    Request,
    RequestStatus,
)
from app.workers.tasks import task_jsm_add_comment, task_send_clarification_email

router = APIRouter(tags=["thread"])

_REVIEWER_ROLES = {Role.POD_REVIEWER, Role.PRODUCT_MANAGER, Role.ADMIN}


class MessageCreate(BaseModel):
    body: str
    is_internal: bool = False


class ClarifyPayload(BaseModel):
    body: str


class MessageResponse(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    author_email: str
    author_name: str
    body: str
    is_internal: bool
    message_type: str
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
        message_type=MessageType.COMMENT,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    await db.commit()

    jsm_body = f"**{user.name}** ({user.email}):\n\n{payload.body}"
    task_jsm_add_comment.delay(str(request_id), jsm_body, not is_internal)

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
    db.add(AuditLog(
        request_id=req.id,
        actor_oid=user.oid,
        actor_email=user.email,
        action="clarification_requested",
        previous_value=str(prev_status),
        new_value=str(RequestStatus.AWAITING_INFO),
    ))
    await db.flush()
    await db.refresh(msg)
    await db.commit()

    task_send_clarification_email.delay(str(request_id), payload.body)
    task_jsm_add_comment.delay(
        str(request_id),
        f"**{user.name}** ({user.email}) requested clarification:\n\n{payload.body}",
        True,
    )

    return MessageResponse.model_validate(msg)
