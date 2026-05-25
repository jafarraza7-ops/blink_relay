from __future__ import annotations

import hashlib
import hmac
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.request import AuditLog, Request as BlinkRequest, RequestStatus
from app.workers.tasks import task_close_jsm_ticket, task_jsm_add_comment, task_send_status_notification

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["webhook"])

# Jira status → Blink Relay status mapping
# "To Do" is intentionally excluded — the request is already Approved when the
# Jira ticket is created; no status change needed on ticket creation.
_JIRA_TO_STATUS: dict[str, RequestStatus] = {
    "Selected for Development": RequestStatus.IN_REVIEW,
    "In Progress":              RequestStatus.IN_PROGRESS,
    "Done":                     RequestStatus.COMPLETED,
    "Closed":                   RequestStatus.CLOSED,
}


def _verify_jira_signature(body: bytes, signature: str) -> bool:
    if not settings.JIRA_WEBHOOK_SECRET:
        return True  # skip verification in local dev
    expected = hmac.new(
        settings.JIRA_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/webhook/jira", status_code=status.HTTP_200_OK)
async def jira_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: str = Header(default=""),
) -> dict:
    body = await request.body()
    if not _verify_jira_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    event = payload.get("webhookEvent", "")

    if event not in ("jira:issue_updated",):
        return {"received": True, "processed": False}

    issue = payload.get("issue", {})
    issue_key = issue.get("key", "")
    jira_status = issue.get("fields", {}).get("status", {}).get("name", "")

    if not issue_key or not jira_status:
        return {"received": True, "processed": False}

    # Find the Blink Relay request linked to this Jira ticket
    result = await db.execute(
        select(BlinkRequest).where(BlinkRequest.jira_ticket_key == issue_key)
    )
    req = result.scalar_one_or_none()
    if not req:
        logger.info("Jira webhook: no request found for ticket %s", issue_key)
        return {"received": True, "processed": False}

    new_status = _JIRA_TO_STATUS.get(jira_status)
    if not new_status or req.status == new_status:
        return {"received": True, "processed": False, "reason": "no_status_change"}

    prev = req.status
    req.status = new_status
    db.add(AuditLog(
        request_id=req.id,
        actor_oid="jira-webhook",
        actor_email="jira@system",
        action="jira_status_sync",
        previous_value=str(prev),
        new_value=str(new_status),
    ))
    await db.commit()  # always commit before firing tasks
    logger.info("Synced %s → %s via Jira webhook (was %s)", issue_key, new_status, prev)

    # Notify the requestor of every status change driven by the Jira ticket
    try:
        task_send_status_notification.delay(str(req.id))
    except Exception:
        logger.warning("task_send_status_notification raised in eager mode — non-fatal", exc_info=True)

    if new_status == RequestStatus.IN_PROGRESS:
        jsm_msg = (
            f"Good news — implementation has started on your request.\n\n"
            f"Jira ticket: {issue_key} is now *In Progress*."
        )
        try:
            task_jsm_add_comment.delay(str(req.id), jsm_msg, True)
        except Exception:
            logger.warning("task_jsm_add_comment raised in eager mode — non-fatal", exc_info=True)

    elif new_status in (RequestStatus.COMPLETED, RequestStatus.CLOSED):
        resolution = (
            f"Implementation complete — Jira ticket {issue_key} has been marked *{jira_status}*.\n\n"
            f"Thank you for raising this request. Your request is now resolved."
        )
        try:
            task_close_jsm_ticket.delay(str(req.id), resolution)
        except Exception:
            logger.warning("task_close_jsm_ticket raised in eager mode — non-fatal", exc_info=True)

    return {"received": True, "processed": True, "ticket": issue_key, "new_status": str(new_status)}
