"""email_tasks.py — Celery tasks for email delivery."""
from __future__ import annotations

import asyncio
from celery import shared_task
from app.services.email_service import get_email_login_template
from app.services.notification_service import NotificationService


def _run(coro):
    """Run an async coroutine from a Celery task (sync or eager context)."""
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


@shared_task(bind=True, max_retries=3)
def task_send_email_login_link(self, email: str, login_url: str, user_name: str = "Requestor"):
    """Send email login link. Retries up to 3 times with exponential backoff.

    Args:
        email: Recipient email address
        login_url: Full URL with token for user to click
        user_name: User's name for personalization (defaults to "Requestor")
    """
    async def _send():
        html_content = get_email_login_template(login_url, user_name)
        await NotificationService().send_email(
            to=email,
            subject="Your Blink Relay Login Link",
            body_html=html_content,
        )

    try:
        _run(_send())
    except Exception as exc:
        # Retry with exponential backoff: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def task_send_status_update_email(self, email: str, reference_id: str, title: str, old_status: str, new_status: str, user_name: str, request_url: str):
    """Send request status update notification.

    Args:
        email: Recipient email address
        reference_id: Request reference ID
        title: Request title
        old_status: Previous status
        new_status: New status
        user_name: Name of the recipient
        request_url: URL to view the request
    """
    async def _send():
        from app.services.email_service import get_status_update_template
        html_content = get_status_update_template(reference_id, title, old_status, new_status, user_name, request_url)
        await NotificationService().send_email(
            to=email,
            subject=f"[Blink Relay] Status Update: {reference_id}",
            body_html=html_content,
        )

    try:
        _run(_send())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def task_send_new_message_email(self, email: str, reference_id: str, title: str, author_name: str, message_preview: str, user_name: str, request_url: str):
    """Send new message notification.

    Args:
        email: Recipient email address
        reference_id: Request reference ID
        title: Request title
        author_name: Who sent the message
        message_preview: First 100 chars of message
        user_name: Name of the recipient
        request_url: URL to view the conversation
    """
    async def _send():
        from app.services.email_service import get_new_message_template
        html_content = get_new_message_template(reference_id, title, author_name, message_preview, user_name, request_url)
        await NotificationService().send_email(
            to=email,
            subject=f"[Blink Relay] New Message: {reference_id}",
            body_html=html_content,
        )

    try:
        _run(_send())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def task_send_request_creation_email(self, email: str, reference_id: str, title: str, request_type: str, priority: str, user_name: str, request_url: str):
    """Send request creation confirmation email.

    Args:
        email: Recipient email address
        reference_id: Request reference ID
        title: Request title
        request_type: Type of request (Feature or Defect)
        priority: Priority level (Critical, High, Medium, Low)
        user_name: Name of the requestor
        request_url: URL to view the request
    """
    async def _send():
        from app.services.email_service import get_request_creation_template
        html_content = get_request_creation_template(reference_id, title, request_type, priority, user_name, request_url)
        await NotificationService().send_email(
            to=email,
            subject=f"[Blink Relay] Request Submitted: {reference_id}",
            body_html=html_content,
        )

    try:
        _run(_send())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def task_send_request_cancellation_email(self, email: str, reference_id: str, title: str, user_name: str, cancellation_date: str):
    """Send request cancellation notification email.

    Args:
        email: Recipient email address
        reference_id: Request reference ID
        title: Request title
        user_name: Name of the person who cancelled the request
        cancellation_date: Date the request was cancelled
    """
    async def _send():
        from app.services.email_service import get_request_cancellation_template
        html_content = get_request_cancellation_template(reference_id, title, user_name, cancellation_date)
        await NotificationService().send_email(
            to=email,
            subject=f"[Blink Relay] Request Cancelled: {reference_id}",
            body_html=html_content,
        )

    try:
        _run(_send())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def task_send_pending_reminder_email(self, email: str, reference_id: str, title: str, submitter_name: str, created_at: str):
    """Send PM reminder email about request pending review for 72+ hours.

    Reminder is sent once every 24 hours to all PMs if a request remains in
    SUBMITTED or IN_REVIEW status without a status update for 72+ hours.

    Args:
        email: PM email address
        reference_id: Request reference ID
        title: Request title
        submitter_name: Name of the requestor who submitted the request
        created_at: ISO format timestamp when the request was created
    """
    async def _send():
        from app.services.email_service import get_pending_reminder_template
        html_content = get_pending_reminder_template(reference_id, title, submitter_name, created_at)
        await NotificationService().send_email(
            to=email,
            subject=f"[Blink Relay] Action Required: Pending Request {reference_id}",
            body_html=html_content,
        )

    try:
        _run(_send())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def task_send_claim_notification(self, request_id: str, pm_name: str, pm_email: str):
    """Notify all PMs that someone claimed a request.

    Sends a single email to all PMs (except the one who claimed it) to prevent duplicate effort.

    Args:
        request_id: UUID of the request being claimed
        pm_name: Name of the PM who claimed the request
        pm_email: Email of the PM who claimed the request
    """
    async def _send():
        import uuid
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.request import Request
        from app.models.auth import User
        from app.services.email_service import get_claim_notification_template

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Request).where(Request.id == uuid.UUID(request_id)))
            req = result.scalar_one_or_none()

            if not req:
                return

            # Get all PMs except the one who claimed it
            pm_result = await db.execute(select(User).where(User.roles.astext.contains("ProductManager")))
            pms = pm_result.scalars().all()
            other_pm_emails = [pm.email for pm in pms if pm.email != pm_email]

            # Send single email to all other PMs
            if other_pm_emails:
                html_content = get_claim_notification_template(
                    req.reference_id or str(req.id),
                    req.title,
                    pm_name,
                    req.priority.value
                )
                await NotificationService().send_email(
                    to=other_pm_emails,
                    subject=f"[Blink Relay] {pm_name} is working on {req.reference_id or req.id}",
                    body_html=html_content,
                )

    try:
        _run(_send())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def task_send_unclaim_notification(self, request_id: str, pm_name: str):
    """Notify all PMs that a PM released a claimed request.

    Sends a single email to all PMs so they know the request is available.

    Args:
        request_id: UUID of the request being released
        pm_name: Name of the PM who released the claim
    """
    async def _send():
        import uuid
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.request import Request
        from app.models.auth import User
        from app.services.email_service import get_unclaim_notification_template

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Request).where(Request.id == uuid.UUID(request_id)))
            req = result.scalar_one_or_none()

            if not req:
                return

            # Get all PMs
            pm_result = await db.execute(select(User).where(User.roles.astext.contains("ProductManager")))
            pms = pm_result.scalars().all()
            pm_emails = [pm.email for pm in pms]

            # Send single email to all PMs
            if pm_emails:
                html_content = get_unclaim_notification_template(
                    req.reference_id or str(req.id),
                    req.title,
                    pm_name
                )
                await NotificationService().send_email(
                    to=pm_emails,
                    subject=f"[Blink Relay] {req.reference_id or req.id} is now available",
                    body_html=html_content,
                )

    try:
        _run(_send())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
