"""
One-off script: add approver info to existing Jira tickets.

For every request with a Jira ticket, looks up the 'approved' audit-log entry
to find who approved it, then posts a comment on the Jira ticket with that info.
"""
from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    from sqlalchemy import select

    from app.core.database import db_session
    from app.models.request import AuditLog, Request
    from app.services.jira_service import JiraService

    jira = JiraService()

    async with db_session() as db:
        result = await db.execute(
            select(Request).where(Request.jira_ticket_key.isnot(None))
        )
        requests = result.scalars().all()

        # Load all relevant audit logs in one query
        request_ids = [r.id for r in requests]
        logs_result = await db.execute(
            select(AuditLog).where(
                AuditLog.request_id.in_(request_ids),
                AuditLog.action == "approved",
            ).order_by(AuditLog.created_at.asc())
        )
        all_logs = logs_result.scalars().all()

    # Map request_id → most recent approval audit log
    approval_by_request: dict = {}
    for log in all_logs:
        approval_by_request[log.request_id] = log

    if not requests:
        logger.info("No requests with Jira tickets found.")
        return

    logger.info("Found %d request(s) with Jira tickets.", len(requests))

    for req in requests:
        jira_key = req.jira_ticket_key
        ref = req.reference_id or str(req.id)
        log = approval_by_request.get(req.id)

        if not log:
            logger.warning("  %s (%s): no approval audit log found — skipping", ref, jira_key)
            continue

        approver_name = log.actor_email  # fallback
        # actor_email is always set; actor_oid is a UUID string not a display name.
        # Use actor_email as the identifier since we don't store display name in audit logs.
        comment = (
            f"*Approved by:* {log.actor_email}\n"
            f"*Approval date:* {log.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
        )

        try:
            await jira.add_comment(jira_key, comment)
            logger.info("  ✓ %s (%s) — approver comment added (%s)", ref, jira_key, log.actor_email)
        except Exception as exc:
            logger.warning("  ✗ %s (%s) — failed: %s", ref, jira_key, exc)

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
