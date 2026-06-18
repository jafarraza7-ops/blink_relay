"""
workers/tasks.py — Celery background tasks for Blink Relay.

All tasks are registered with autoretry_for=(Exception,) so transient failures
(network blips, Jira API timeouts) are retried automatically.

Async / event-loop design
--------------------------
Celery workers are synchronous, but the service layer (JiraService, JsmService,
NotificationService) uses async/await. The _run() helper bridges the two:
  - If called from within a running event loop (eager mode inside FastAPI),
    it executes the coroutine in a fresh thread to avoid "loop already running".
  - If called from a real Celery worker (no running loop), it creates a new loop.

Eager mode (local dev)
-----------------------
When CELERY_TASK_ALWAYS_EAGER=True, .delay() calls run synchronously in-process.
Every API endpoint commits to the DB before calling .delay() so that eager tasks
see the updated row immediately — they read from the same DB connection.

Tasks overview:
  route_request_to_pod            — AI keyword routing for pod=UNKNOWN requests.
  task_create_jira_ticket         — Create the Jira implementation ticket on approval.
  task_jira_add_comment           — Post a comment to the Jira ticket.
  task_sync_attachments           — Upload stored blobs to Jira/JSM as attachments.
  task_create_jsm_ticket          — Create the customer-facing JSM ticket on submission.
  task_jsm_add_comment            — Post a comment to the JSM ticket.
  task_close_jsm_ticket           — Resolve the JSM ticket (idempotent).
  task_send_status_notification   — Email the requestor on any status change.
  task_send_email                 — Low-level generic email dispatch.
  task_send_clarification_email   — Email requestor when a PM asks a question.
  task_notify_pm_clarification_response — Email the PM when the requestor responds.
  sync_jira_status                — Poll-based fallback to sync Jira status (webhook alternative).
"""
from __future__ import annotations

import logging
import uuid

from app.workers.celery_app import celery_app
from app.workers.utils import run_async as _run

logger = logging.getLogger(__name__)


# ── Pod routing ───────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.route_request_to_pod",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def route_request_to_pod(self, request_id: str) -> dict:
    """Auto-assign a pod to a request submitted with pod=UNKNOWN.

    Uses keyword/ML scoring; only commits the result when confidence >= 65%
    to avoid mis-routing requests where the business problem is ambiguous.
    """
    from app.core.database import task_db_session as db_session
    from app.models.request import Pod, Request
    from app.services.pod_routing_service import PodRoutingService

    async def _route():
        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                logger.error("route_request_to_pod: request %s not found", request_id)
                return {}

            if req.pod != Pod.UNKNOWN:
                return {"pod": str(req.pod), "auto_routed": False}

            routing = PodRoutingService()
            result = routing.route(req.title, req.business_problem, req.request_type)

            if result.confidence >= 0.65 and result.pod != Pod.UNKNOWN:
                req.pod = result.pod
                await db.commit()
                logger.info(
                    "Auto-routed request %s → %s (confidence %.2f, keywords: %s)",
                    request_id,
                    result.pod,
                    result.confidence,
                    result.matched_keywords,
                )
                return {
                    "pod": str(result.pod),
                    "confidence": result.confidence,
                    "auto_routed": True,
                    "keywords": result.matched_keywords,
                }
            return {"pod": str(req.pod), "auto_routed": False, "confidence": result.confidence}

    return _run(_route())


# ── Jira ticket creation task ─────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_create_jira_ticket",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def task_create_jira_ticket(
    self,
    request_id: str,
    project_override: str | None = None,
    epic_title: str | None = None,
    approver_name: str | None = None,
    approver_email: str | None = None,
) -> dict:
    """Create a Jira implementation ticket for an approved request.

    When JIRA_MOCK=true, writes a fake ticket key to the DB so the rest of
    the workflow (JSM linking, attachment sync, comments) can still be tested.

    After creation:
      - Jira ↔ JSM tickets are linked via Jira issue links.
      - A cross-reference comment is posted to each ticket.
      - All stored attachments are synced to both tickets.
    """
    from app.core.config import get_settings as _get_settings
    from app.core.database import task_db_session as db_session
    from app.models.request import Request
    from app.services.pod_routing_service import PodRoutingService

    _settings = _get_settings()

    async def _create():
        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                logger.error("task_create_jira_ticket: request %s not found", request_id)
                return {}

            routing = PodRoutingService()
            project_key = project_override or routing.get_jira_project(req.pod)

            if _settings.JIRA_MOCK:
                fake_key = f"{project_key}-MOCK-{request_id[:8].upper()}"
                fake_url = f"https://blinkcharging.atlassian.net/browse/{fake_key}"
                req.jira_ticket_key = fake_key
                req.jira_ticket_url = fake_url
                logger.info("JIRA_MOCK: returning fake ticket %s for request %s", fake_key, request_id)
                return {"key": fake_key, "url": fake_url, "mock": True}

            from app.services.jira_service import JiraService
            title = epic_title or req.title
            jira = JiraService()

            assignee_account_id: str | None = None
            assignee_email = routing.get_assignee_email(req.pod)
            if assignee_email:
                assignee_account_id = await jira.get_account_id_by_email(assignee_email)
                if assignee_account_id:
                    logger.info("Assigning ticket to pod assignee %s (%s)", assignee_email, assignee_account_id)
                else:
                    logger.warning("Pod assignee %s has no Jira account — using default", assignee_email)

            # IMPROVEMENT: Add timeout to Jira API calls with graceful degradation
            # Reasoning: Jira API can be slow; timeout prevents approve from blocking
            import asyncio
            try:
                ticket = await asyncio.wait_for(
                    jira.create_ticket(
                        project_key=project_key,
                        title=title,
                        description=req.business_problem,
                        request_type=str(req.request_type),
                        priority=str(req.priority),
                        submitter_name=req.submitter_name,
                        submitter_email=req.submitter_email,
                        reference_id=req.reference_id,
                        affected_area=req.affected_area,
                        region=", ".join(req.region) if isinstance(req.region, list) else str(req.region),
                        expected_outcome=req.expected_outcome,
                        steps_to_reproduce=req.steps_to_reproduce,
                        additional_context=req.additional_context,
                        component=str(req.pod) if req.pod else None,
                        assignee_account_id=assignee_account_id,
                        approver_name=approver_name,
                        approver_email=approver_email,
                    ),
                    timeout=20  # 20 second timeout for Jira ticket creation
                )

                req.jira_ticket_key = ticket["key"]
                req.jira_ticket_url = ticket["url"]
                # Commit now so subsequent tasks (jsm comment, attachment sync) can
                # read jira_ticket_key from the DB in eager mode.
                await db.commit()
                logger.info("Jira ticket %s created for request %s", ticket["key"], request_id)
            except asyncio.TimeoutError:
                logger.warning(
                    "Jira ticket creation timed out for request %s (>20s) — skipping link/comment steps",
                    request_id,
                )
                await db.commit()
                return {}

            # ── Link TP ↔ REL tickets ─────────────────────────────────────────
            jsm_key = req.jsm_ticket_key
            jsm_url = req.jsm_ticket_url or (
                f"{_settings.JIRA_BASE_URL}/browse/{jsm_key}" if jsm_key else None
            )
            tp_key = ticket["key"]
            tp_url = ticket["url"]

            if jsm_key:
                try:
                    await jira.link_issues(tp_key, jsm_key)
                    logger.info("Linked %s ↔ %s", tp_key, jsm_key)
                except Exception:
                    logger.warning("Failed to link %s ↔ %s — non-fatal", tp_key, jsm_key, exc_info=True)

                # Comment on the REL (submission) ticket with the TP link.
                try:
                    await jira.add_comment(
                        jsm_key,
                        f"Implementation ticket created: {tp_key}\n{tp_url}\n\n"
                        f"This request has been approved and is now being tracked in Jira.",
                    )
                    logger.info("Added TP link comment to %s", jsm_key)
                except Exception:
                    logger.warning("Failed to comment on %s — non-fatal", jsm_key, exc_info=True)

                # Comment on the TP (implementation) ticket with the REL link.
                try:
                    await jira.add_comment(
                        tp_key,
                        f"Linked to Blink Relay submission ticket: {jsm_key}\n{jsm_url}\n\n"
                        f"Originally submitted via Blink Relay (ref: {req.reference_id}).",
                    )
                    logger.info("Added REL link comment to %s", tp_key)
                except Exception:
                    logger.warning("Failed to comment on %s — non-fatal", tp_key, exc_info=True)

            # ── Blink Relay audit trail message ───────────────────────────────
            from app.models.request import AuditLog as _AuditLog, Message, MessageType
            audit_body = (
                f"Implementation ticket **{tp_key}** created in Jira: {tp_url}"
                + (f"\nLinked to submission ticket **{jsm_key}**: {jsm_url}" if jsm_key else "")
            )
            db.add(Message(
                request_id=req.id,
                author_email="system@blink-relay",
                author_name="Blink Relay",
                body=audit_body,
                is_internal=True,
                message_type=MessageType.COMMENT,
            ))
            db.add(_AuditLog(
                request_id=req.id,
                actor_oid="system",
                actor_email="system@blink-relay",
                action="jira_ticket_created",
                new_value=ticket["key"],
                event_data={"ticket_key": ticket["key"], "ticket_url": ticket["url"]},
            ))
            await db.commit()

            return ticket

    result = _run(_create())

    # Sync attachments to the new Jira ticket (runs outside _run to avoid nested loop issues).
    if result and result.get("key"):
        try:
            task_sync_attachments.delay(request_id)
        except Exception:
            logger.warning("task_sync_attachments raised — non-fatal", exc_info=True)

    return result


# ── Jira comment task ─────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_jira_add_comment",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def task_jira_add_comment(self, request_id: str, body: str) -> dict:
    """Add a comment to the Jira ticket linked to a Blink Relay request."""
    from app.core.config import get_settings as _gs
    from app.core.database import task_db_session as db_session
    from app.models.request import Request

    async def _comment():
        _s = _gs()
        if _s.JIRA_MOCK:
            logger.info("JIRA_MOCK: skipping Jira comment for request %s", request_id)
            return {"skipped": True, "mock": True}

        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                logger.error("task_jira_add_comment: request %s not found", request_id)
                return {}
            if not req.jira_ticket_key:
                logger.info("task_jira_add_comment: no Jira ticket for request %s — skipping", request_id)
                return {"skipped": True}

            from app.services.jira_service import JiraService
            jira = JiraService()
            result = await jira.add_comment(req.jira_ticket_key, body)
            logger.info("Jira comment %s added to %s", result.get("id"), req.jira_ticket_key)
            return result

    return _run(_comment())


# ── Attachment sync task ───────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_sync_attachments",
    max_retries=2,
    default_retry_delay=15,
    autoretry_for=(Exception,),
)
def task_sync_attachments(
    self,
    request_id: str,
    attachment_ids: list[str] | None = None,
) -> dict:
    """Upload stored attachments to the linked Jira and/or JSM tickets.

    If ``attachment_ids`` is given, only those attachments are synced (used
    when new files are uploaded after the tickets already exist). When None,
    all attachments for the request are synced (used after ticket creation).
    """
    from sqlalchemy import select

    from app.core.config import get_settings as _gs
    from app.core.database import task_db_session as db_session
    from app.models.request import Attachment, Request
    from app.services.jira_service import JiraService
    from app.services.storage_service import StorageService

    async def _sync():
        _s = _gs()
        if _s.JIRA_MOCK:
            logger.info("JIRA_MOCK: skipping attachment sync for request %s", request_id)
            return {"skipped": True, "mock": True}

        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                logger.error("task_sync_attachments: request %s not found", request_id)
                return {}

            q = select(Attachment).where(Attachment.request_id == req.id)
            if attachment_ids:
                ids = [uuid.UUID(a) for a in attachment_ids]
                q = q.where(Attachment.id.in_(ids))
            result = await db.execute(q)
            attachments = result.scalars().all()

            if not attachments:
                return {"skipped": True, "reason": "no_attachments"}

            storage = StorageService()
            jira = JiraService()
            synced = 0

            for att in attachments:
                try:
                    data = await storage.download_bytes(att.blob_name)
                except Exception:
                    logger.warning("task_sync_attachments: failed to download %s", att.blob_name, exc_info=True)
                    continue

                for ticket_key in filter(None, [req.jira_ticket_key, req.jsm_ticket_key]):
                    try:
                        await jira.upload_attachment(ticket_key, att.filename, att.content_type, data)
                        synced += 1
                    except Exception:
                        logger.warning(
                            "task_sync_attachments: failed to upload '%s' to %s",
                            att.filename, ticket_key, exc_info=True,
                        )

            logger.info("task_sync_attachments: synced %d attachment(s) for request %s", synced, request_id)
            return {"synced": synced}

    return _run(_sync())


# ── JSM tasks ─────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_create_jsm_ticket",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def task_create_jsm_ticket(self, request_id: str) -> dict:
    """Create a JSM customer-facing ticket for the given Blink Relay request."""
    from app.core.database import task_db_session as db_session
    from app.models.request import Request
    from app.services.jsm_service import JsmService

    async def _create():
        from app.core.config import get_settings as _gs
        _s = _gs()
        if not _s.JSM_MOCK and not (_s.JIRA_EMAIL and _s.JIRA_API_TOKEN):
            logger.warning("task_create_jsm_ticket: JIRA credentials not set — skipping JSM ticket creation")
            return {"skipped": True}

        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                logger.error("task_create_jsm_ticket: request %s not found", request_id)
                return {}
            if req.jsm_ticket_key:
                logger.info("JSM ticket already exists for %s: %s", request_id, req.jsm_ticket_key)
                return {"key": req.jsm_ticket_key, "url": req.jsm_ticket_url, "skipped": True}

            if _s.JSM_MOCK:
                import random as _r
                fake_key = f"BLR-{_r.randint(1000, 9999)}"
                fake_url = f"https://blinkcharging.atlassian.net/servicedesk/customer/portal/1/{fake_key}"
                req.jsm_ticket_key = fake_key
                req.jsm_ticket_url = fake_url
                logger.info("JSM_MOCK: fake ticket %s created for request %s", fake_key, request_id)
                return {"key": fake_key, "url": fake_url}

            # Use Jira REST API directly (issue creation) — avoids needing JSM agent role.
            import base64 as _b64
            import httpx as _httpx

            region_str = ', '.join(req.region) if isinstance(req.region, list) else str(req.region)
            description_adf = {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": f"Blink Relay reference: {req.reference_id or request_id}"}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": f"Business problem:\n{req.business_problem}"}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": f"Affected area: {req.affected_area} | Region: {region_str} | Priority: {req.priority} | POD: {req.pod} | Submitted by: {req.submitter_email}"}]},
                ]
            }
            token = _b64.b64encode(f"{_s.JIRA_EMAIL}:{_s.JIRA_API_TOKEN}".encode()).decode()
            headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json", "Accept": "application/json"}
            payload = {
                "fields": {
                    "project": {"key": "REL"},
                    "issuetype": {"id": "10250"},
                    "summary": f"[{req.reference_id}] {req.request_type}: {req.title}",
                    "description": description_adf,
                }
            }
            async with _httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{_s.JIRA_BASE_URL.rstrip('/')}/rest/api/3/issue",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code != 201:
                    raise RuntimeError(f"Jira issue creation failed {resp.status_code}: {resp.text}")
                data = resp.json()
                key = data["key"]
                url = f"{_s.JIRA_BASE_URL.rstrip('/')}/browse/{key}"
                req.jsm_ticket_key = key
                req.jsm_ticket_url = url
                await db.commit()
                logger.info("Jira ticket %s created for request %s", key, request_id)
                from app.models.request import AuditLog as _AuditLog
                db.add(_AuditLog(
                    request_id=req.id,
                    actor_oid="system",
                    actor_email="system@blink-relay",
                    action="jsm_ticket_created",
                    new_value=key,
                    event_data={"ticket_key": key, "ticket_url": url},
                ))
                await db.commit()
                return {"key": key, "url": url}

    return _run(_create())


@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_jsm_add_comment",
    max_retries=3,
    default_retry_delay=15,
    autoretry_for=(Exception,),
)
def task_jsm_add_comment(self, request_id: str, body: str, public: bool = True) -> dict:
    """Add a comment to the JSM ticket for the given Blink Relay request.

    No-ops gracefully when the request has no JSM ticket yet (e.g. JSM creation
    task is still queued behind this one).
    """
    from app.core.config import get_settings as _get_settings
    _s = _get_settings()
    # JSM portal comments are not supported (using Jira REST API for ticket creation).
    logger.info("task_jsm_add_comment: skipping for request %s (no JSM portal access)", request_id)
    return {"skipped": True}
    # Dead code below kept for future JSM portal integration:

    from app.core.database import task_db_session as db_session
    from app.models.request import Request
    from app.services.jsm_service import JsmService

    async def _comment():
        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                logger.error("task_jsm_add_comment: request %s not found", request_id)
                return {}
            if not req.jsm_ticket_key:
                logger.warning(
                    "task_jsm_add_comment: request %s has no JSM ticket yet — skipping",
                    request_id,
                )
                return {"skipped": True}

            jsm = JsmService()
            result = await jsm.add_comment(req.jsm_ticket_key, body, public=public)
            logger.info(
                "JSM comment %s added to %s (public=%s)",
                result.get("id"),
                req.jsm_ticket_key,
                public,
            )
            return result

    return _run(_comment())


@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_close_jsm_ticket",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def task_close_jsm_ticket(self, request_id: str, resolution_comment: str) -> dict:
    """Resolve the JSM ticket and notify the requestor.

    Idempotent: if the JSM ticket has already been resolved (``jsm_resolved_at``
    set) this is a no-op, so a duplicate webhook from Jira can't double-close.
    """
    from datetime import datetime, timezone

    from app.core.database import task_db_session as db_session
    from app.models.request import Request
    from app.services.jsm_service import JsmService
    from app.services.notification_service import NotificationService

    async def _close():
        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                logger.error("task_close_jsm_ticket: request %s not found", request_id)
                return {}
            if not req.jsm_ticket_key:
                logger.warning(
                    "task_close_jsm_ticket: request %s has no JSM ticket — skipping",
                    request_id,
                )
                return {"skipped": True}
            if req.jsm_resolved_at:
                logger.info(
                    "task_close_jsm_ticket: %s already resolved at %s — skipping",
                    req.jsm_ticket_key,
                    req.jsm_resolved_at,
                )
                return {"skipped": True, "already_resolved": True}

            jsm = JsmService()
            try:
                await jsm.resolve(req.jsm_ticket_key, resolution_comment)
            except Exception:
                logger.warning(
                    "task_close_jsm_ticket: failed to resolve %s — skipping JSM close",
                    req.jsm_ticket_key, exc_info=True,
                )
                return {"skipped": True, "error": "jsm_resolve_failed"}
            req.jsm_resolved_at = datetime.now(timezone.utc)
            logger.info("JSM ticket %s resolved", req.jsm_ticket_key)

            # Notify the requestor that the JSM ticket has been closed.
            try:
                notifier = NotificationService()
                await notifier.notify_jsm_closed(
                    req.submitter_email,
                    req.title,
                    req.reference_id or str(req.id),
                    req.jsm_ticket_key,
                    req.jsm_ticket_url or "",
                    resolution_comment,
                    req.jira_ticket_key,
                    req.jira_ticket_url,
                )
            except Exception:
                logger.exception("Failed to send JSM-closed notification — non-fatal")

            return {"key": req.jsm_ticket_key, "resolved": True}

    return _run(_close())


# ── Notification tasks ────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_send_status_notification",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def task_send_status_notification(self, request_id: str) -> None:
    """Send status notification emails on any request status change.

    - Submitter always receives the notification.
    - PM group (pms@blinkcharging.com) is CC'd on all status changes so
      every member of the TP/JSM space stays informed.
    - The claiming PM is also notified individually if they are not already
      covered by the group email.
    """
    from app.core.database import task_db_session as db_session
    from app.models.request import Request, RequestStatus
    from app.services.notification_service import NotificationService
    from app.services.pod_routing_service import PodRoutingService
    from app.services.email_group_service import get_pm_group_emails

    async def _notify():
        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                return

            routing = PodRoutingService()
            notifier = NotificationService()
            ref = req.reference_id or str(req.id)

            # --- Notify requestor ---
            if req.status == RequestStatus.SUBMITTED:
                await notifier.notify_submitted(req.submitter_email, req.title, ref)
            elif req.status == RequestStatus.APPROVED:
                await notifier.notify_approved(req.submitter_email, req.title, ref, req.jira_ticket_url)
            elif req.status == RequestStatus.IN_PROGRESS:
                await notifier.notify_in_progress(
                    req.submitter_email, req.title, ref, req.jira_ticket_url
                )
            elif req.status == RequestStatus.COMPLETED:
                await notifier.notify_completed(
                    req.submitter_email, req.title, ref,
                    jira_url=req.jira_ticket_url,
                    jsm_url=req.jsm_ticket_url,
                )
            elif req.status == RequestStatus.REJECTED:
                await notifier.notify_rejected(
                    req.submitter_email, req.title, ref,
                    req.rejection_reason or "No reason provided",
                    req.rejection_comment,
                )
            elif req.status == RequestStatus.CLOSED:
                await notifier.notify_closed(
                    req.submitter_email, req.title, ref,
                    jira_url=req.jira_ticket_url,
                    jsm_url=req.jsm_ticket_url,
                )
            else:
                await notifier.notify_status_change(
                    req.submitter_email, req.title, ref, str(req.status)
                )

            # --- Notify PM group (TP/JSM space members) for all non-submission changes ---
            if req.status != RequestStatus.SUBMITTED:
                pm_group_email, _ = await get_pm_group_emails(db)
                if pm_group_email:
                    await notifier.notify_status_change(
                        pm_group_email, req.title, ref, str(req.status)
                    )

            # --- Notify the claiming PM individually if set and not submitter ---
            if req.claimed_by_email and req.claimed_by_email != req.submitter_email:
                await notifier.notify_status_change(
                    req.claimed_by_email, req.title, ref, str(req.status)
                )

            webhook_url = routing.get_teams_webhook(req.pod)
            if webhook_url:
                await notifier.send_teams_notification(webhook_url, {
                    "title": f"Request updated: {ref}",
                    "text": f"**{req.title}** → {req.status}",
                })

    _run(_notify())


# ── Polling-based Jira sync (webhook fallback) ────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.sync_jira_status",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def sync_jira_status(self, request_id: str) -> dict:
    """Poll Jira for the current ticket status and update the relay request.

    This is a fallback for environments where the Jira webhook is unavailable.
    Note: this mapping includes "To Do" → Approved, unlike the webhook handler,
    because polling runs after the ticket already exists.
    """
    from app.core.database import task_db_session as db_session
    from app.models.request import AuditLog, Request, RequestStatus
    from app.services.jira_service import JiraService

    _JIRA_TO_STATUS: dict[str, RequestStatus] = {
        "To Do": RequestStatus.APPROVED,
        "In Progress": RequestStatus.IN_PROGRESS,
        "Done": RequestStatus.COMPLETED,
        "Closed": RequestStatus.CLOSED,
    }

    async def _sync():
        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req or not req.jira_ticket_key:
                return {"synced": False}

            jira = JiraService()
            data = await jira.get_ticket(req.jira_ticket_key)
            jira_status = data.get("fields", {}).get("status", {}).get("name", "")

            new_status = _JIRA_TO_STATUS.get(jira_status)
            if new_status and req.status != new_status:
                prev = req.status
                req.status = new_status
                db.add(AuditLog(
                    request_id=req.id,
                    actor_oid="jira-sync",
                    actor_email="jira@system",
                    action="jira_status_sync",
                    previous_value=str(prev),
                    new_value=str(new_status),
                ))
                logger.info("Synced %s → %s via Jira poll", req.jira_ticket_key, new_status)
                return {"synced": True, "new_status": str(new_status)}
            return {"synced": False, "jira_status": jira_status}

    return _run(_sync())


@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_send_email",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def task_send_email(self, to: str, subject: str, body_html: str) -> None:
    """Low-level task to send a raw HTML email. Prefer the specific notify_* tasks
    for status-driven emails — this is used for one-off or ad-hoc messages."""
    from app.services.notification_service import NotificationService

    async def _send():
        await NotificationService().send_email(to, subject, body_html)

    _run(_send())


@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_send_clarification_email",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def task_send_clarification_email(self, request_id: str, question_body: str) -> None:
    """Email the requestor when a PM sends a clarification question."""
    from app.core.config import get_settings as _gs
    from app.core.database import task_db_session as db_session
    from app.models.request import Request
    from app.services.notification_service import NotificationService

    _s = _gs()

    async def _send():
        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                return
            portal_link = f"{_s.FRONTEND_URL}/respond/{request_id}"
            await NotificationService().notify_awaiting_info(
                req.submitter_email,
                req.title,
                req.reference_id or str(req.id),
                question_body,
                portal_link=portal_link,
            )

    _run(_send())


@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_notify_pm_clarification_response",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def task_notify_pm_clarification_response(self, request_id: str) -> None:
    """Email the PM who last sent a clarification question when the requestor responds."""
    from app.core.config import get_settings as _gs
    from app.core.database import task_db_session as db_session
    from app.models.request import Message, MessageType, Request
    from app.services.notification_service import NotificationService

    _s = _gs()

    async def _notify():
        from sqlalchemy import select

        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                return
            q = (
                select(Message)
                .where(
                    Message.request_id == req.id,
                    Message.message_type == MessageType.CLARIFICATION_QUESTION,
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            result = await db.execute(q)
            last_question = result.scalar_one_or_none()
            if not last_question:
                return
            portal_link = f"{_s.FRONTEND_URL}/requests/{request_id}"
            await NotificationService().notify_clarification_received(
                last_question.author_email,
                req.title,
                req.reference_id or str(req.id),
                portal_link=portal_link,
            )

    _run(_notify())


# ── Escalation alerts ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_send_escalation_digest",
    max_retries=2,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def task_send_escalation_digest(self) -> dict:
    """Send daily digest of escalated requests (AwaitingInfo >7 days) to all PMs.

    Scheduled to run daily at 9 AM.
    """
    from app.core.database import task_db_session as db_session
    from app.services.escalation_service import get_escalation_summary
    from app.services.email_group_service import get_pm_group_emails
    from app.services.notification_service import NotificationService

    async def _send_digest():
        async with db_session() as db:
            summary = await get_escalation_summary(db, days_threshold=7)

            if summary["total"] == 0:
                logger.info("No escalated requests found — skipping digest")
                return {"skipped": True, "reason": "no_escalations"}

            _, pm_emails = await get_pm_group_emails(db)
            if not pm_emails:
                logger.warning("No PM emails configured — cannot send escalation digest")
                return {"error": "no_pm_emails"}

            from app.core.config import get_settings as _gs
            from jinja2 import Template
            from pathlib import Path

            _s = _gs()

            # Load template
            template_path = Path(__file__).parent.parent / "services" / "email_templates" / "escalation_digest.html"
            with open(template_path) as f:
                template_html = f.read()

            template = Template(template_html)
            body_html = template.render(
                count=summary["total"],
                oldest_days=summary["oldest_days"],
                by_priority=summary["by_priority"],
                by_pod=summary["by_pod"],
                requests=summary["requests"],
                base_url=_s.FRONTEND_URL,
                now=__import__('datetime').datetime.utcnow(),
            )

            # Send to all PMs
            ns = NotificationService()
            for pm_email in pm_emails:
                try:
                    await ns.send_email(
                        to=pm_email,
                        subject=f"⚠️ Escalation Alert: {summary['total']} request(s) waiting for response",
                        body_html=body_html,
                    )
                except Exception as e:
                    logger.error(f"Failed to send escalation digest to {pm_email}: {e}")

            logger.info(
                f"Sent escalation digest to {len(pm_emails)} PM(s): "
                f"{summary['total']} escalated request(s), "
                f"oldest waiting {summary['oldest_days']} days"
            )

            return {
                "sent_to": len(pm_emails),
                "escalations": summary["total"],
                "oldest_days": summary["oldest_days"],
            }

    return _run(_send_digest())


# ── 72-Hour No-Action Reminder Task ───────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_send_72hr_no_action_reminder",
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def task_send_72hr_no_action_reminder(self) -> dict:
    """Send daily reminder email to PMs for requests with no action for 72+ hours.

    Finds all requests that:
    - Have not been claimed by a PM (claimed_by_oid is NULL)
    - Have not been updated in 72+ hours (updated_at < now - 72 hours)
    - Are in actionable status (Submitted, InReview, AwaitingInfo, Approved)
    - Either have never received a reminder, or last reminder was >24h ago

    Sends one email per PM listing all unclaimed idle requests assigned to their pod.
    Updates reminder_sent_at for each request to prevent duplicate reminders.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import and_, or_, select

    from app.core.config import get_settings as _gs
    from app.core.database import task_db_session as db_session
    from app.models.request import Request, RequestStatus, User
    from app.services.notification_service import NotificationService

    _s = _gs()

    async def _send_reminders():
        now = datetime.now(timezone.utc)
        threshold_72h = now - timedelta(hours=72)
        threshold_24h = now - timedelta(hours=24)

        async with db_session() as db:
            # Find all requests with no action for 72+ hours and no PM claim
            stmt = select(Request).where(
                and_(
                    Request.updated_at < threshold_72h,
                    Request.claimed_by_oid.is_(None),
                    Request.status.in_([
                        RequestStatus.SUBMITTED,
                        RequestStatus.IN_REVIEW,
                        RequestStatus.AWAITING_INFO,
                        RequestStatus.APPROVED,
                    ]),
                    or_(
                        Request.reminder_sent_at.is_(None),
                        Request.reminder_sent_at < threshold_24h,
                    ),
                )
            )
            idle_requests = (await db.execute(stmt)).scalars().all()

            if not idle_requests:
                logger.info("No idle unclaimed requests found for 72-hour reminder")
                return {"requests_found": 0, "pms_notified": 0}

            # Get all PMs
            pm_stmt = select(User).where(User.roles.contains("ProductManager"))
            pms = (await db.execute(pm_stmt)).scalars().all()
            pm_emails = [pm.email for pm in pms if pm.email]

            if not pm_emails:
                logger.warning("No PMs found to send 72-hour reminder")
                return {"requests_found": len(idle_requests), "pms_notified": 0}

            # Build email content
            ns = NotificationService()
            request_list_html = ""
            for req in idle_requests:
                days_idle = (now - req.updated_at).days
                status_badge = f'<span style="display:inline-block; padding:4px 8px; border-radius:4px; background:#f0f0f0; font-size:12px; font-weight:500;">{req.status}</span>'
                request_list_html += f'''
                <tr>
                  <td style="padding:8px; border-bottom:1px solid #eee;">
                    <strong>{req.reference_id or req.id}</strong><br/>
                    <a href="{_s.FRONTEND_URL}/requests/{req.id}" style="color:#0066cc; text-decoration:none;">{req.title}</a>
                  </td>
                  <td style="padding:8px; border-bottom:1px solid #eee;">{req.pod}</td>
                  <td style="padding:8px; border-bottom:1px solid #eee; text-align:center;">{status_badge}</td>
                  <td style="padding:8px; border-bottom:1px solid #eee; text-align:center;">{days_idle} days</td>
                </tr>
                '''

            body_html = f'''
            <html>
            <head></head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
              <p>Hi,</p>
              <p>The following requests have not been updated in 72+ hours and are waiting for PM action.</p>
              <p><strong>Please claim and action these requests:</strong></p>
              <table style="width:100%; border-collapse:collapse; margin:20px 0;">
                <thead>
                  <tr style="background:#f5f5f5; border-bottom:2px solid #ddd;">
                    <th style="padding:8px; text-align:left; font-weight:bold;">Request</th>
                    <th style="padding:8px; text-align:left; font-weight:bold;">Pod</th>
                    <th style="padding:8px; text-align:center; font-weight:bold;">Status</th>
                    <th style="padding:8px; text-align:center; font-weight:bold;">Days Idle</th>
                  </tr>
                </thead>
                <tbody>
                  {request_list_html}
                </tbody>
              </table>
              <p><a href="{_s.FRONTEND_URL}/dashboard" style="color:#0066cc; text-decoration:none; font-weight:bold;">View Dashboard</a></p>
              <hr style="border:none; border-top:1px solid #ddd; margin:20px 0;">
              <p style="font-size:12px; color:#666;">This is an automated reminder sent daily at {now.strftime('%I:%M %p UTC')}.</p>
            </body>
            </html>
            '''

            # Send to all PMs
            sent_count = 0
            for pm_email in pm_emails:
                try:
                    await ns.send_email(
                        to=pm_email,
                        subject=f"⏰ 72-Hour No-Action Reminder: {len(idle_requests)} request(s) waiting",
                        body_html=body_html,
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send 72-hour reminder to {pm_email}: {e}")

            # Update reminder_sent_at for all idle requests
            for req in idle_requests:
                req.reminder_sent_at = now
            await db.commit()

            logger.info(
                f"Sent 72-hour no-action reminder to {sent_count} PM(s) for {len(idle_requests)} request(s)"
            )

            return {
                "requests_found": len(idle_requests),
                "pms_notified": sent_count,
                "requests_updated": len(idle_requests),
            }

    return _run(_send_reminders())
