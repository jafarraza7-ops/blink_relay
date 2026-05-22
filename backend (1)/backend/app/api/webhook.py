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
from app.workers.tasks import task_close_jsm_ticket

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["webhook"])

# Jira status → Blink Relay status mapping
_JIRA_TO_STATUS: dict[str, RequestStatus] = {
    "To Do": RequestStatus.APPROVED,
    "In Progress": RequestStatus.IN_PROGRESS,
    "Done": RequestStatus.COMPLETED,
    "Closed": RequestStatus.CLOSED,
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
    if new_status and req.status != new_status:
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
        logger.info("Synced %s → %s via Jira webhook", issue_key, new_status)

        # Auto-close the JSM ticket and notify the requestor when the dev
        # ticket reaches a terminal state.
        if new_status in (RequestStatus.COMPLETED, RequestStatus.CLOSED):
            await db.commit()  # commit before eager task reads the same DB
            resolution = (
                f"Implementation complete in {issue_key} ({jira_status}). "
                f"Thanks for raising this — your request is now resolved."
            )
            task_close_jsm_ticket.delay(str(req.id), resolution)

    return {"received": True, "processed": True, "ticket": issue_key}
