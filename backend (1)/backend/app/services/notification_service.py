from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _cta_button(url: str, label: str) -> str:
    return (
        f'<p><a href="{url}" style="display:inline-block;padding:10px 20px;'
        f'background:#1d4ed8;color:#fff;text-decoration:none;border-radius:6px">'
        f'{label}</a></p>'
    ) if url else ""


def _html_wrap(body: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;color:#1a1a1a;max-width:600px;margin:0 auto;padding:24px">
{body}
<hr style="margin-top:32px;border:none;border-top:1px solid #e5e7eb"/>
<p style="font-size:12px;color:#6b7280">Blink Relay · Internal Tech Request System</p>
</body></html>"""


class NotificationService:
    async def _send_smtp(self, to: str, subject: str, body_html: str) -> None:
        import aiosmtplib

        sender = settings.SMTP_FROM or settings.SMTP_USER
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.attach(MIMEText(body_html, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASS,
            start_tls=True,
        )
        logger.info("SMTP email sent to %s: %s", to, subject)

    async def _send_graph(self, to: str, subject: str, body_html: str) -> None:
        url = f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/token"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, data={
                "grant_type": "client_credentials",
                "client_id": settings.AZURE_CLIENT_ID,
                "client_secret": settings.AZURE_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            })
            resp.raise_for_status()
            token = resp.json()["access_token"]

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": [{"emailAddress": {"address": to}}],
            }
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.GRAPH_API_BASE_URL}/users/{settings.JIRA_EMAIL}/sendMail",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if not resp.is_success:
                logger.error("Graph sendMail failed: %s %s", resp.status_code, resp.text)
            else:
                logger.info("Graph email sent to %s: %s", to, subject)

    async def send_email(self, to: str, subject: str, body_html: str) -> None:
        try:
            if settings.EMAIL_BACKEND == "smtp":
                await self._send_smtp(to, subject, body_html)
            else:
                await self._send_graph(to, subject, body_html)
        except Exception:
            logger.exception("send_email error — swallowing to avoid blocking caller")

    async def notify_submitted(self, submitter_email: str, title: str, reference_id: str) -> None:
        subject = f"[Blink Relay] Request received: {reference_id}"
        body = _html_wrap(f"""
        <h2>Your request has been received</h2>
        <p>Thank you for submitting <strong>{title}</strong>.</p>
        <p>Your reference number is <strong>{reference_id}</strong>. A product manager will review it shortly.</p>
        """)
        await self.send_email(submitter_email, subject, body)

    async def notify_status_change(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        new_status: str,
    ) -> None:
        subject = f"[Blink Relay] {reference_id} status updated: {new_status}"
        body = _html_wrap(f"""
        <h2>Request status updated</h2>
        <p>Your request <strong>{title}</strong> (ref: <strong>{reference_id}</strong>) has been updated.</p>
        <p><strong>New status:</strong> {new_status}</p>
        """)
        await self.send_email(submitter_email, subject, body)

    async def notify_awaiting_info(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        reviewer_message: str,
        portal_link: str = "",
    ) -> None:
        link_html = _cta_button(portal_link, "Respond to this request")
        subject = f"[Blink Relay] {reference_id} — additional information needed"
        body = _html_wrap(f"""
        <h2>Additional information required</h2>
        <p>Your request <strong>{title}</strong> (ref: <strong>{reference_id}</strong>) needs more details.</p>
        <p style="font-weight:600">The reviewer asked:</p>
        <blockquote style="border-left:4px solid #e5e7eb;padding-left:12px;color:#374151">{reviewer_message}</blockquote>
        {link_html}
        <p style="color:#6b7280;font-size:13px">Please provide the requested information so the review can continue.</p>
        """)
        await self.send_email(submitter_email, subject, body)

    async def notify_clarification_received(
        self,
        pm_email: str,
        title: str,
        reference_id: str,
        portal_link: str = "",
    ) -> None:
        link_html = _cta_button(portal_link, "View response")
        subject = f"[Blink Relay] {reference_id} — requestor has responded"
        body = _html_wrap(f"""
        <h2>Requestor has responded</h2>
        <p><strong>{title}</strong> (ref: <strong>{reference_id}</strong>) has received additional information from the requestor.</p>
        {link_html}
        """)
        await self.send_email(pm_email, subject, body)

    async def notify_approved(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        jira_url: str | None,
    ) -> None:
        jira_link = _cta_button(jira_url or "", "View Jira ticket")
        subject = f"[Blink Relay] {reference_id} approved"
        body = _html_wrap(f"""
        <h2>Request approved</h2>
        <p>Your request <strong>{title}</strong> (ref: <strong>{reference_id}</strong>) has been approved and scheduled for development.</p>
        {jira_link}
        """)
        await self.send_email(submitter_email, subject, body)

    async def notify_rejected(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        reason: str,
        comment: str | None,
    ) -> None:
        comment_block = f"<p><em>{comment}</em></p>" if comment else ""
        subject = f"[Blink Relay] {reference_id} not approved"
        body = _html_wrap(f"""
        <h2>Request not approved</h2>
        <p>Your request <strong>{title}</strong> (ref: <strong>{reference_id}</strong>) was not approved.</p>
        <p><strong>Reason:</strong> {reason}</p>
        {comment_block}
        """)
        await self.send_email(submitter_email, subject, body)

    async def notify_closed(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        jira_url: str | None = None,
        jsm_url: str | None = None,
    ) -> None:
        jira_link = f'<p><a href="{jira_url}">View implementation ticket</a></p>' if jira_url else ""
        jsm_link = f'<p><a href="{jsm_url}">View service request</a></p>' if jsm_url else ""
        subject = f"[Blink Relay] {reference_id} — request closed"
        body = _html_wrap(f"""
        <h2>Request closed</h2>
        <p>Your request <strong>{title}</strong> (ref: <strong>{reference_id}</strong>) has been closed.</p>
        {jira_link}
        {jsm_link}
        <p style="color:#6b7280;font-size:13px">If you believe this was closed in error, please open a new request.</p>
        """)
        await self.send_email(submitter_email, subject, body)

    async def notify_jsm_closed(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        jsm_ticket_key: str,
        jsm_ticket_url: str,
        resolution: str,
        jira_ticket_key: str | None = None,
        jira_ticket_url: str | None = None,
    ) -> None:
        jsm_link = (
            f'<p><a href="{jsm_ticket_url}">View service request {jsm_ticket_key}</a></p>'
            if jsm_ticket_url else f"<p>Service request: {jsm_ticket_key}</p>"
        )
        jira_link = (
            f'<p><a href="{jira_ticket_url}">Implementation ticket {jira_ticket_key}</a></p>'
            if jira_ticket_url and jira_ticket_key else ""
        )
        subject = f"[Blink Relay] {reference_id} — service request resolved"
        body = _html_wrap(f"""
        <h2>Your service request has been resolved</h2>
        <p>Your request <strong>{title}</strong> (ref: <strong>{reference_id}</strong>) is now closed.</p>
        <p><strong>Resolution:</strong></p>
        <blockquote style="border-left:4px solid #16a34a;padding-left:12px;color:#374151">{resolution}</blockquote>
        {jsm_link}
        {jira_link}
        <p>If you believe this was closed in error, reply to this email or open a new request.</p>
        """)
        await self.send_email(submitter_email, subject, body)

    async def send_teams_notification(self, webhook_url: str, message: dict) -> None:
        if not webhook_url:
            logger.debug("No Teams webhook configured — skipping notification")
            return
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(webhook_url, json=message)
                if not resp.is_success:
                    logger.error("Teams notification failed: %s", resp.status_code)
        except Exception:
            logger.exception("send_teams_notification error — swallowing")
