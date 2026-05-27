"""
api/webhook.py — Jira webhook receiver for bi-directional status sync.

Jira pushes an event to POST /api/webhook/jira whenever an issue is updated.
This endpoint:
  1. Verifies the HMAC-SHA256 signature (skipped in local dev if JIRA_WEBHOOK_SECRET is unset).
  2. Looks up the Blink Relay request by jira_ticket_key.
  3. Maps the Jira status to a Blink Relay RequestStatus via _JIRA_TO_STATUS.
  4. Updates the request status, writes an AuditLog and Message row.
  5. Fires async tasks to email the requestor and update the JSM ticket.

For COMPLETED/CLOSED statuses the JSM ticket is resolved (not just commented on)
so the customer-facing service-desk ticket is closed in sync with the Jira ticket.
"""
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
from app.models.request import AuditLog, Message, MessageType, Request as BlinkRequest, RequestStatus
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
    """Return True if the request body matches the HMAC-SHA256 signature sent by Jira.
    Returns True unconditionally in local dev when JIRA_WEBHOOK_SECRET is not configured."""
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

    # Only process issue-updated events. All other event types (e.g. project
    # events, comment events) are acknowledged but ignored.
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

    # Skip unmapped statuses (e.g. "To Do" — no relay action needed on ticket creation)
    # and skip if the relay status is already up-to-date (idempotent on duplicate events).
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

    _webhook_messages: dict[RequestStatus, str] = {
        RequestStatus.IN_REVIEW:   f"Jira ticket {issue_key} moved to **{jira_status}** — request is now **In Review**.",
        RequestStatus.IN_PROGRESS: f"Jira ticket {issue_key} is now **In Progress** — implementation has started.",
        RequestStatus.COMPLETED:   f"Jira ticket {issue_key} has been marked **{jira_status}** — implementation is complete.",
        RequestStatus.CLOSED:      f"Jira ticket {issue_key} is **Closed** — this request has been resolved.",
    }
    msg_body = _webhook_messages.get(new_status, f"Status updated to **{new_status}** via Jira ticket {issue_key}.")
    db.add(Message(
        request_id=req.id,
        author_oid="jira-webhook",
        author_email="jira@system",
        author_name="Jira",
        body=msg_body,
        is_internal=False,
        message_type=MessageType.STATUS_CHANGE,
    ))
    await db.commit()  # always commit before firing tasks
    logger.info("Synced %s → %s via Jira webhook (was %s)", issue_key, new_status, prev)

    # Notify the requestor of every status change driven by the Jira ticket
    try:
        task_send_status_notification.delay(str(req.id))
    except Exception:
        logger.warning("task_send_status_notification raised in eager mode — non-fatal", exc_info=True)

    # Post a JSM comment for every Jira status transition so the requestor
    # always sees the latest progress on their service-desk ticket.
    _jsm_messages: dict[RequestStatus, str] = {
        RequestStatus.IN_REVIEW: (
            f"Your request is being scoped for development.\n\n"
            f"Jira ticket *{issue_key}* has been selected for the development queue."
        ),
        RequestStatus.IN_PROGRESS: (
            f"Good news — implementation has started on your request.\n\n"
            f"Jira ticket *{issue_key}* is now *In Progress*."
        ),
        RequestStatus.COMPLETED: (
            f"Implementation is complete — Jira ticket *{issue_key}* has been marked *{jira_status}*.\n\n"
            f"Thank you for raising this request. Your request is now resolved."
        ),
        RequestStatus.CLOSED: (
            f"This request has been closed — Jira ticket *{issue_key}* is *{jira_status}*.\n\n"
            f"Thank you for using Blink Relay."
        ),
    }

    jsm_msg = _jsm_messages.get(
        new_status,
        f"Update on your request — Jira ticket *{issue_key}* status changed to *{jira_status}*.",
    )

    # For terminal statuses we close the JSM ticket (which also posts the comment
    # internally). For all other transitions we post a comment so the requestor
    # sees progress without the ticket being prematurely closed.
    if new_status in (RequestStatus.COMPLETED, RequestStatus.CLOSED):
        try:
            task_close_jsm_ticket.delay(str(req.id), jsm_msg)
        except Exception:
            logger.warning("task_close_jsm_ticket raised in eager mode — non-fatal", exc_info=True)
    else:
        try:
            task_jsm_add_comment.delay(str(req.id), jsm_msg, True)
        except Exception:
            logger.warning("task_jsm_add_comment raised in eager mode — non-fatal", exc_info=True)

    return {"received": True, "processed": True, "ticket": issue_key, "new_status": str(new_status)}
