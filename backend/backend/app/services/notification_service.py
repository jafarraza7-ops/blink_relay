from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Tuple

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Branded email template helpers ────────────────────────────────────────────

def _render_email(
    title: str,
    body_paragraphs: List[str],
    info_rows: Optional[List[Tuple[str, str]]] = None,
    cta_url: Optional[str] = None,
    cta_label: Optional[str] = None,
    greeting: Optional[str] = None,
    footer_note: Optional[str] = None,
    extra_block: Optional[str] = None,
) -> str:
    """Render a fully branded Blink Relay email using table-based layout.

    Args:
        title: Large heading shown below the logo header.
        body_paragraphs: List of paragraph strings shown in the body.
        info_rows: Optional list of (label, value) tuples for the info box.
        cta_url: Optional CTA button URL.
        cta_label: Optional CTA button label text.
        greeting: Optional greeting line (e.g. "Hi,"). Omitted if None.
        footer_note: Optional small-print paragraph above the divider footer.
        extra_block: Optional raw HTML block inserted after the info box
                     (used for blockquotes, reviewer messages, etc.).
    Returns:
        Complete HTML email string with inline styles.
    """
    # Greeting block
    greeting_html = (
        f'<p style="font-size:15px;color:#374151;margin:0 0 12px 0">{greeting}</p>'
        if greeting else ""
    )

    # Body paragraphs
    body_html = "".join(
        f'<p style="font-size:15px;color:#374151;line-height:1.6;margin:0 0 12px 0">{p}</p>'
        for p in body_paragraphs
    )

    # Info box
    info_box_html = ""
    if info_rows:
        rows_html = "".join(
            f"""<tr>
              <td style="padding:4px 8px 4px 0;vertical-align:top">
                <span style="color:#6b7280;font-size:14px">{label}:</span>
              </td>
              <td style="padding:4px 0">
                <strong style="font-size:14px;color:#111827">{value}</strong>
              </td>
            </tr>"""
            for label, value in info_rows
        )
        info_box_html = f"""
        <div style="background:#f3f4f6;border-left:4px solid #1d4ed8;border-radius:4px;padding:16px;margin:16px 0">
          <table width="100%" cellpadding="0" cellspacing="0">
            {rows_html}
          </table>
        </div>"""

    # Extra block (blockquote, etc.)
    extra_html = extra_block or ""

    # CTA button
    cta_html = ""
    if cta_url and cta_label:
        cta_html = f"""
        <div style="text-align:center;margin:24px 0">
          <a href="{cta_url}"
             style="display:inline-block;background:#1e3a5f;color:#ffffff;text-decoration:none;padding:12px 32px;border-radius:9999px;font-weight:600;font-size:15px">{cta_label}</a>
        </div>"""

    # Footer note
    footer_note_html = (
        f'<p style="font-size:13px;color:#6b7280;line-height:1.5;margin:0 0 16px 0">{footer_note}</p>'
        if footer_note else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background-color:#f9fafb;font-family:Arial,Helvetica,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f9fafb">
    <tr>
      <td align="center" style="padding:32px 16px">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:8px;overflow:hidden;max-width:600px">

          <!-- Logo / Header -->
          <tr>
            <td style="padding:24px 32px 0 32px">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="vertical-align:middle">
                    <span style="display:inline-block;background:#1d4ed8;border-radius:8px;padding:6px 10px;font-size:18px;line-height:1">&#9889;</span>
                  </td>
                  <td style="vertical-align:middle;padding-left:10px">
                    <span style="font-size:18px;font-weight:700;color:#1e3a5f">Blink Relay</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Title -->
          <tr>
            <td style="padding:24px 32px 0 32px">
              <h1 style="font-size:24px;font-weight:700;color:#111827;margin:0">{title}</h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:20px 32px 0 32px">
              {greeting_html}
              {body_html}
              {info_box_html}
              {extra_html}
              {cta_html}
            </td>
          </tr>

          <!-- Footer note + divider -->
          <tr>
            <td style="padding:16px 32px 32px 32px">
              {footer_note_html}
              <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0"/>
              <p style="font-size:12px;color:#6b7280;margin:4px 0">Blink Relay &bull; Product Intake System</p>
              <p style="font-size:12px;color:#6b7280;margin:4px 0">This is an automated message. Please do not reply to this email.</p>
              <p style="font-size:12px;color:#6b7280;margin:4px 0">&copy; 2026 Blink Charging. All rights reserved.</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


class NotificationService:
    async def _send_smtp(self, to: str | list[str], subject: str, body_html: str, cc: str | list[str] | None = None) -> None:
        """Send email via SMTP with timeout protection.

        Supports single/multiple recipients and optional CC recipients.

        IMPROVEMENT: Add 10-second timeout to prevent frontend request timeouts
        Problem: SMTP operations could hang indefinitely, blocking API responses
        Solution: Use asyncio.wait_for with 10s timeout; log warning but don't fail request
        Impact: Ensures API returns within 30s frontend timeout even if email is slow
        """
        import aiosmtplib
        import asyncio

        sender = settings.SMTP_FROM or settings.SMTP_USER
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender

        # Handle both single and multiple recipients
        if isinstance(to, list):
            msg["To"] = ", ".join(to)
            recipients = to
        else:
            msg["To"] = to
            recipients = [to]

        # Handle CC recipients
        cc_recipients = []
        if cc:
            if isinstance(cc, list):
                msg["Cc"] = ", ".join(cc)
                cc_recipients = cc
            else:
                msg["Cc"] = cc
                cc_recipients = [cc]

        msg.attach(MIMEText(body_html, "html"))

        # SMTP send requires all recipients (to + cc)
        all_recipients = recipients + cc_recipients

        try:
            await asyncio.wait_for(
                aiosmtplib.send(
                    msg,
                    hostname=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    username=settings.SMTP_USER,
                    password=settings.SMTP_PASS,
                    start_tls=True,
                    recipients=all_recipients,
                ),
                timeout=10  # 10 second timeout for SMTP operations
            )
            logger.info("SMTP email sent to %s (cc: %s): %s", ", ".join(recipients), ", ".join(cc_recipients) if cc_recipients else "none", subject)
        except asyncio.TimeoutError:
            # GRACEFUL DEGRADATION: Log but don't fail - user's action completes even if email is slow
            logger.warning("SMTP timeout sending to %s (cc: %s), continuing anyway", ", ".join(recipients), ", ".join(cc_recipients) if cc_recipients else "none")

    async def _send_graph(self, to: str | list[str], subject: str, body_html: str, cc: str | list[str] | None = None) -> None:
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

        # Handle both single and multiple TO recipients
        if isinstance(to, list):
            to_recipients = [{"emailAddress": {"address": addr}} for addr in to]
            recipients_str = ", ".join(to)
        else:
            to_recipients = [{"emailAddress": {"address": to}}]
            recipients_str = to

        # Handle CC recipients
        cc_recipients = []
        cc_str = ""
        if cc:
            if isinstance(cc, list):
                cc_recipients = [{"emailAddress": {"address": addr}} for addr in cc]
                cc_str = ", ".join(cc)
            else:
                cc_recipients = [{"emailAddress": {"address": cc}}]
                cc_str = cc

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": to_recipients,
            }
        }

        # Add CC recipients if provided
        if cc_recipients:
            payload["message"]["ccRecipients"] = cc_recipients

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.GRAPH_API_BASE_URL}/users/{settings.JIRA_EMAIL}/sendMail",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if not resp.is_success:
                logger.error("Graph sendMail failed: %s %s", resp.status_code, resp.text)
            else:
                cc_log = f" (cc: {cc_str})" if cc_str else ""
                logger.info("Graph email sent to %s%s: %s", recipients_str, cc_log, subject)

    async def send_email(self, to: str | list[str], subject: str, body_html: str, cc: str | list[str] | None = None) -> None:
        """Send email via configured backend (SMTP or Microsoft Graph).

        Supports single/multiple recipients and optional CC recipients.

        IMPROVEMENT: Enhanced error logging with recipient and error details
        Ensures silent failures are discoverable in logs without blocking the API request.
        """
        try:
            if settings.EMAIL_BACKEND == "smtp":
                await self._send_smtp(to, subject, body_html, cc=cc)
            else:
                await self._send_graph(to, subject, body_html, cc=cc)
        except Exception as e:
            # IMPROVEMENT: Log recipient and error message for debugging
            # Exception is caught to prevent blocking API responses; errors are logged for monitoring
            recipients_str = ", ".join(to) if isinstance(to, list) else to
            cc_str = f", cc={', '.join(cc) if isinstance(cc, list) else cc}" if cc else ""
            logger.exception(f"send_email error to {recipients_str}{cc_str}: {str(e)} — swallowing to avoid blocking caller")

    # ── Branded notify_* methods ───────────────────────────────────────────────

    async def notify_submitted(self, submitter_email: str, title: str, reference_id: str) -> None:
        subject = f"[Blink Relay] Request Submitted Successfully — {reference_id}"
        body = _render_email(
            title="Request Submitted Successfully",
            greeting="Hi,",
            body_paragraphs=[
                "Your request has been successfully submitted to Blink Relay and is now in the review queue. "
                "Our team will review it shortly and keep you updated on the progress.",
            ],
            info_rows=[
                ("Reference ID", reference_id),
                ("Title", title),
            ],
            cta_url=f"{settings.FRONTEND_URL}/requests",
            cta_label="View Your Request",
            footer_note=(
                "You'll receive email updates as your request progresses through the review workflow. "
                "If you have any questions, please reach out to the Blink team."
            ),
        )
        await self.send_email(submitter_email, subject, body)

    async def notify_status_change(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        new_status: str,
    ) -> None:
        subject = f"[Blink Relay] Status Updated — {reference_id}"
        body = _render_email(
            title="Request Status Updated",
            greeting="Hi,",
            body_paragraphs=[
                f"Your request status has been updated to <strong>{new_status}</strong>.",
            ],
            info_rows=[
                ("Reference ID", reference_id),
                ("Title", title),
                ("New Status", new_status),
            ],
            cta_url=f"{settings.FRONTEND_URL}/requests",
            cta_label="View Your Request",
        )
        await self.send_email(submitter_email, subject, body)

    async def notify_awaiting_info(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        reviewer_message: str,
        portal_link: str = "",
    ) -> None:
        subject = f"[Blink Relay] Additional Information Needed — {reference_id}"
        reviewer_block = (
            f'<div style="background:#f3f4f6;border-left:4px solid #6b7280;border-radius:4px;'
            f'padding:16px;margin:16px 0;font-size:14px;color:#374151;line-height:1.6">'
            f'<strong style="display:block;margin-bottom:8px;color:#111827">Message from reviewer:</strong>'
            f'{reviewer_message}</div>'
        )
        body = _render_email(
            title="Additional Information Needed",
            greeting="Hi,",
            body_paragraphs=[
                "Your request requires additional information before we can proceed with the review.",
            ],
            info_rows=[
                ("Reference ID", reference_id),
                ("Title", title),
            ],
            extra_block=reviewer_block,
            cta_url=portal_link or f"{settings.FRONTEND_URL}/requests",
            cta_label="Respond to This Request",
            footer_note="Please provide the requested information so the review can continue.",
        )
        await self.send_email(submitter_email, subject, body)

    async def notify_clarification_received(
        self,
        pm_email: str,
        title: str,
        reference_id: str,
        portal_link: str = "",
    ) -> None:
        subject = f"[Blink Relay] Requestor Has Responded — {reference_id}"
        body = _render_email(
            title="Requestor Has Responded",
            greeting="Hi,",
            body_paragraphs=[
                f"The requestor has provided additional information for <strong>{title}</strong>. "
                "Please review their response and continue the review process.",
            ],
            info_rows=[
                ("Reference ID", reference_id),
                ("Title", title),
            ],
            cta_url=portal_link or f"{settings.FRONTEND_URL}/requests",
            cta_label="View Response",
        )
        await self.send_email(pm_email, subject, body)

    async def notify_approved(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        jira_url: str | None,
    ) -> None:
        subject = f"[Blink Relay] Request Approved — {reference_id}"
        info_rows: List[Tuple[str, str]] = [
            ("Reference ID", reference_id),
            ("Title", title),
        ]
        if jira_url:
            info_rows.append(("Jira Ticket", f'<a href="{jira_url}" style="color:#1d4ed8">{jira_url}</a>'))
        body = _render_email(
            title="Request Approved",
            greeting="Hi,",
            body_paragraphs=[
                "Great news! Your request has been reviewed and approved. "
                "Our development team will begin working on it shortly.",
            ],
            info_rows=info_rows,
            cta_url=jira_url or f"{settings.FRONTEND_URL}/requests",
            cta_label="View Jira Ticket" if jira_url else "View Your Request",
            footer_note="You'll receive further updates as implementation progresses.",
        )
        await self.send_email(submitter_email, subject, body)

    async def notify_in_progress(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        jira_url: str | None = None,
    ) -> None:
        subject = f"[Blink Relay] Implementation Started — {reference_id}"
        body = _render_email(
            title="Implementation In Progress",
            greeting="Hi,",
            body_paragraphs=[
                "Work has begun on your approved request. Our development team is actively working on it.",
            ],
            info_rows=[
                ("Reference ID", reference_id),
                ("Title", title),
            ],
            cta_url=jira_url or f"{settings.FRONTEND_URL}/requests",
            cta_label="View Jira Ticket" if jira_url else "View Your Request",
            footer_note="You'll receive an update once implementation is complete.",
        )
        await self.send_email(submitter_email, subject, body)

    async def notify_completed(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        jira_url: str | None = None,
        jsm_url: str | None = None,
    ) -> None:
        subject = f"[Blink Relay] Request Completed — {reference_id}"
        body = _render_email(
            title="Implementation Complete",
            greeting="Hi,",
            body_paragraphs=[
                "We are pleased to inform you that the implementation of your request has been completed successfully.",
            ],
            info_rows=[
                ("Reference ID", reference_id),
                ("Title", title),
            ],
            cta_url=jira_url or f"{settings.FRONTEND_URL}/requests",
            cta_label="View Implementation Ticket" if jira_url else "View Your Request",
            footer_note="Thank you for using Blink Relay. If you have further needs, feel free to submit a new request.",
        )
        await self.send_email(submitter_email, subject, body)

    async def notify_rejected(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        reason: str,
        comment: str | None,
    ) -> None:
        subject = f"[Blink Relay] Request Not Approved — {reference_id}"
        comment_block = ""
        if comment:
            comment_block = (
                f'<div style="background:#fef9f0;border-left:4px solid #f59e0b;border-radius:4px;'
                f'padding:16px;margin:16px 0;font-size:14px;color:#374151;line-height:1.6">'
                f'<strong style="display:block;margin-bottom:8px;color:#111827">Reviewer comment:</strong>'
                f'{comment}</div>'
            )
        body = _render_email(
            title="Request Not Approved",
            greeting="Hi,",
            body_paragraphs=[
                "Thank you for your submission. After review, we are unable to approve this request at this time.",
            ],
            info_rows=[
                ("Reference ID", reference_id),
                ("Title", title),
                ("Reason", reason),
            ],
            extra_block=comment_block,
            footer_note=(
                "If you have questions or would like to resubmit with more information, "
                "please reach out to your product manager."
            ),
        )
        await self.send_email(submitter_email, subject, body)

    async def notify_closed(
        self,
        submitter_email: str,
        title: str,
        reference_id: str,
        jira_url: str | None = None,
        jsm_url: str | None = None,
    ) -> None:
        subject = f"[Blink Relay] Request Closed — {reference_id}"
        body = _render_email(
            title="Request Closed",
            greeting="Hi,",
            body_paragraphs=[
                f"Your request <strong>{title}</strong> has been closed.",
            ],
            info_rows=[
                ("Reference ID", reference_id),
                ("Title", title),
            ],
            cta_url=jira_url or f"{settings.FRONTEND_URL}/requests",
            cta_label="View Implementation Ticket" if jira_url else "View Your Request",
            footer_note="If you believe this was closed in error, please open a new request.",
        )
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
        subject = f"[Blink Relay] Service Request Resolved — {reference_id}"
        resolution_block = (
            f'<div style="background:#f0fdf4;border-left:4px solid #16a34a;border-radius:4px;'
            f'padding:16px;margin:16px 0;font-size:14px;color:#374151;line-height:1.6">'
            f'<strong style="display:block;margin-bottom:8px;color:#111827">Resolution:</strong>'
            f'{resolution}</div>'
        )
        info_rows: List[Tuple[str, str]] = [
            ("Reference ID", reference_id),
            ("Title", title),
        ]
        if jsm_ticket_key:
            jsm_display = (
                f'<a href="{jsm_ticket_url}" style="color:#1d4ed8">{jsm_ticket_key}</a>'
                if jsm_ticket_url else jsm_ticket_key
            )
            info_rows.append(("Service Request", jsm_display))
        if jira_ticket_key and jira_ticket_url:
            info_rows.append((
                "Implementation Ticket",
                f'<a href="{jira_ticket_url}" style="color:#1d4ed8">{jira_ticket_key}</a>',
            ))
        body = _render_email(
            title="Your Service Request Has Been Resolved",
            greeting="Hi,",
            body_paragraphs=[
                f"Your request <strong>{title}</strong> (ref: <strong>{reference_id}</strong>) is now closed.",
            ],
            info_rows=info_rows,
            extra_block=resolution_block,
            cta_url=jsm_ticket_url or f"{settings.FRONTEND_URL}/requests",
            cta_label="View Service Request",
            footer_note="If you believe this was closed in error, please open a new request.",
        )
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
