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
