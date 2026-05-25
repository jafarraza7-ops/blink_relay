from __future__ import annotations

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    """Run an async coroutine from a Celery task (sync or eager context)."""
    try:
        asyncio.get_running_loop()
        # Called from within a running event loop (eager mode inside FastAPI).
        # Run in a fresh thread to avoid "This event loop is already running".
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=30)
    except RuntimeError:
        # No running loop — safe to create one directly.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.route_request_to_pod",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def route_request_to_pod(self, request_id: str) -> dict:
    from app.core.database import db_session
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
) -> dict:
    from app.core.config import get_settings as _get_settings
    from app.core.database import db_session
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

            ticket = await jira.create_ticket(
                project_key=project_key,
                title=title,
                description=req.business_problem,
                request_type=str(req.request_type),
                priority=str(req.priority),
                submitter_name=req.submitter_name,
                submitter_email=req.submitter_email,
                reference_id=req.reference_id,
                affected_area=req.affected_area,
                region=str(req.region),
                expected_outcome=req.expected_outcome,
                steps_to_reproduce=req.steps_to_reproduce,
                additional_context=req.additional_context,
                component=str(req.pod) if req.pod else None,
                assignee_account_id=assignee_account_id,
            )

            req.jira_ticket_key = ticket["key"]
            req.jira_ticket_url = ticket["url"]
            await db.commit()  # commit before eager tasks read jira_ticket_key
            logger.info("Jira ticket %s created for request %s", ticket["key"], request_id)

            # Mirror the dev-ticket link into the JSM activity log so the
            # requestor sees the link from inside the service-desk portal.
            if req.jsm_ticket_key:
                task_jsm_add_comment.delay(
                    request_id,
                    f"Implementation ticket created: {ticket['key']} — {ticket['url']}",
                    True,  # public
                )

            # Sync all attachments to the new Jira ticket (and JSM if present).
            task_sync_attachments.delay(request_id)

            return ticket

    return _run(_create())


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
    from app.core.database import db_session
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
    from app.core.database import db_session
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
    from app.core.database import db_session
    from app.models.request import Request
    from app.services.jsm_service import JsmService

    async def _create():
        from app.core.config import get_settings as _gs
        _s = _gs()
        if not _s.JSM_MOCK and not (_s.JSM_SERVICE_DESK_ID and _s.JSM_REQUEST_TYPE_ID):
            logger.warning("task_create_jsm_ticket: JSM_REQUEST_TYPE_ID not set — skipping JSM ticket creation")
            return {"skipped": True}

        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                logger.error("task_create_jsm_ticket: request %s not found", request_id)
                return {}
            if req.jsm_ticket_key:
                logger.info("JSM ticket already exists for %s: %s", request_id, req.jsm_ticket_key)
                return {"key": req.jsm_ticket_key, "url": req.jsm_ticket_url, "skipped": True}

            description = (
                f"*Blink Relay reference:* {req.reference_id or request_id}\n\n"
                f"*Business problem:*\n{req.business_problem}\n\n"
                f"*Affected area:* {req.affected_area}\n"
                f"*Region:* {req.region}\n"
                f"*Priority:* {req.priority}\n"
                f"*POD:* {req.pod}"
            )

            jsm = JsmService()
            ticket = await jsm.create_request(
                summary=req.title,
                description=description,
                reporter_email=req.submitter_email,
                reference_id=req.reference_id,
                labels=[f"pod-{str(req.pod).lower()}", f"type-{str(req.request_type).lower()}"],
            )
            req.jsm_ticket_key = ticket["key"]
            req.jsm_ticket_url = ticket["url"]
            logger.info("JSM ticket %s created for request %s", ticket["key"], request_id)
            return ticket

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
    from app.core.database import db_session
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

    from app.core.database import db_session
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


@celery_app.task(
    bind=True,
    name="app.workers.tasks.task_send_status_notification",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def task_send_status_notification(self, request_id: str) -> None:
    from app.core.database import db_session
    from app.models.request import Request, RequestStatus
    from app.services.notification_service import NotificationService
    from app.services.pod_routing_service import PodRoutingService

    async def _notify():
        async with db_session() as db:
            req = await db.get(Request, uuid.UUID(request_id))
            if not req:
                return

            routing = PodRoutingService()
            notifier = NotificationService()
            ref = req.reference_id or str(req.id)

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

            webhook_url = routing.get_teams_webhook(req.pod)
            if webhook_url:
                await notifier.send_teams_notification(webhook_url, {
                    "title": f"Request updated: {ref}",
                    "text": f"**{req.title}** → {req.status}",
                })

    _run(_notify())


@celery_app.task(
    bind=True,
    name="app.workers.tasks.sync_jira_status",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def sync_jira_status(self, request_id: str) -> dict:
    from app.core.database import db_session
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
    from app.core.database import db_session
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
    from app.core.database import db_session
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
