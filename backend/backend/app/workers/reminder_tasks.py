"""
workers/reminder_tasks.py — Scheduled background tasks for automated reminders.

Runs on a schedule (Celery Beat) to check for stale requests and send notifications
to PMs about requests pending review for 72+ hours. Implements deduplication logic
to prevent spamming PMs with multiple reminders in a 24-hour window.

Task overview:
  task_send_pending_request_reminder — Runs daily; finds requests pending 72+ hours
                                       and sends reminder to all PMs once per 24h.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import and_, or_, select

from app.core.database import db_session
from app.models.request import Request, RequestStatus, User
from app.workers.email_tasks import task_send_pending_reminder_email

logger = logging.getLogger(__name__)


from app.workers.utils import run_async as _run


@shared_task
def task_send_pending_request_reminder() -> dict[str, int]:
    """Find requests pending 72+ hours and send reminder emails to all PMs.

    Runs on a schedule (Celery Beat) to identify requests in SUBMITTED or IN_REVIEW
    status that have been waiting for 72+ hours without a status update. Sends a
    reminder email to all PMs with the ProductManager role, one time every 24 hours
    per request (prevents email spam via reminder_sent_at deduplication).

    Deduplication logic:
      - If reminder_sent_at is NULL (never sent), send and set to current timestamp
      - If reminder_sent_at is set and < 24 hours ago, skip (already reminded recently)
      - If reminder_sent_at is set and >= 24 hours ago, send again and update timestamp

    This ensures PMs get periodic reminders if requests remain stale, while avoiding
    multiple emails on the same day for the same request.

    Returns:
        Dictionary with:
          - total_pending: count of requests in SUBMITTED/IN_REVIEW for 72+ hours
          - reminders_sent: count of reminder emails queued (may be > total_pending
                            if multiple PMs exist)
          - errors: count of failures during reminder sending
    """
    async def _check_and_remind() -> dict[str, int]:
        # Thresholds for the 72-hour and 24-hour windows
        cutoff_created = datetime.now(timezone.utc) - timedelta(hours=72)
        cutoff_reminded = datetime.now(timezone.utc) - timedelta(hours=24)

        async with db_session() as db:
            # Find all requests that meet the criteria:
            # 1. Status is SUBMITTED or IN_REVIEW (waiting for PM action)
            # 2. Created more than 72 hours ago (pending for 72+ hours)
            # 3. No reminder sent yet (reminder_sent_at is NULL) OR last reminder was 24+ hours ago
            result = await db.execute(
                select(Request).where(
                    and_(
                        Request.status.in_([RequestStatus.SUBMITTED, RequestStatus.IN_REVIEW]),
                        Request.created_at < cutoff_created,
                        or_(
                            Request.reminder_sent_at.is_(None),
                            Request.reminder_sent_at < cutoff_reminded,
                        ),
                    )
                )
            )
            pending_requests = result.scalars().all()

            logger.info(
                "task_send_pending_request_reminder: Found %d requests pending 72+ hours",
                len(pending_requests),
            )

            # Find all users with ProductManager role
            pm_result = await db.execute(
                select(User).where(User.roles.contains("ProductManager"))
            )
            pms = pm_result.scalars().all()

            if not pms:
                logger.warning(
                    "task_send_pending_request_reminder: No PMs found with ProductManager role"
                )
                return {"total_pending": len(pending_requests), "reminders_sent": 0, "errors": 0}

            logger.info(
                "task_send_pending_request_reminder: Found %d PMs to notify",
                len(pms),
            )

            reminders_sent = 0
            errors = 0

            # Send reminder to each PM for each pending request
            from app.services.notification_service import NotificationService
            from app.services.email_service import get_pending_reminder_template

            for req in pending_requests:
                for pm in pms:
                    try:
                        # Send email directly (eager mode in local dev; queued in production)
                        html_content = get_pending_reminder_template(
                            req.reference_id or str(req.id),
                            req.title,
                            req.submitter_name,
                            req.created_at.isoformat()
                        )
                        await NotificationService().send_email(
                            to=pm.email,
                            subject=f"[Blink Relay] Action Required: Pending Request {req.reference_id or str(req.id)}",
                            body_html=html_content,
                        )
                        reminders_sent += 1

                        logger.debug(
                            "Sent reminder email for PM %s about request %s",
                            pm.email,
                            req.reference_id or str(req.id),
                        )
                    except Exception as e:
                        errors += 1
                        logger.error(
                            "Failed to send reminder email for PM %s, request %s: %s",
                            pm.email,
                            req.reference_id or str(req.id),
                            str(e),
                        )

                # Update reminder_sent_at only if we successfully queued reminders
                # for at least one PM (indicates the request was processed)
                if reminders_sent > 0:
                    req.reminder_sent_at = datetime.now(timezone.utc)
                    await db.flush()  # Flush partial updates

            # Commit all reminder_sent_at updates
            await db.commit()

            logger.info(
                "task_send_pending_request_reminder: Sent %d reminders with %d errors",
                reminders_sent,
                errors,
            )

            return {
                "total_pending": len(pending_requests),
                "reminders_sent": reminders_sent,
                "errors": errors,
            }

    return _run(_check_and_remind())
