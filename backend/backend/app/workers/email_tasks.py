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
            subject=f"Request Submitted: {reference_id}",
            body_html=html_content,
        )

    try:
        _run(_send())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
