"""
One-off script: link existing Jira ↔ JSM ticket pairs.

Finds every request that has both jira_ticket_key and jsm_ticket_key set,
creates the formal issue link, and posts cross-reference comments on both tickets.
Safe to run multiple times — the Jira issueLink API is idempotent for the same pair.
"""
from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.core.database import db_session
    from app.models.request import Request
    from app.services.jira_service import JiraService

    settings = get_settings()
    jira = JiraService()

    async with db_session() as db:
        result = await db.execute(
            select(Request).where(
                Request.jira_ticket_key.isnot(None),
                Request.jsm_ticket_key.isnot(None),
            )
        )
        requests = result.scalars().all()

    if not requests:
        logger.info("No requests found with both Jira and JSM tickets — nothing to do.")
        return

    logger.info("Found %d request(s) to process.", len(requests))

    for req in requests:
        jira_key = req.jira_ticket_key
        jsm_key = req.jsm_ticket_key
        ref = req.reference_id or str(req.id)
        logger.info("Processing %s  Jira=%s  JSM=%s", ref, jira_key, jsm_key)

        # 1. Formal issue link (shows in Issue Links section of both tickets)
        try:
            await jira.link_issues(jira_key, jsm_key)
            logger.info("  ✓ Linked %s ↔ %s", jira_key, jsm_key)
        except Exception as exc:
            logger.warning("  ✗ Link failed: %s", exc)

        # 2. Comment on Jira ticket pointing to JSM
        jsm_url = req.jsm_ticket_url or f"{settings.JIRA_BASE_URL}/browse/{jsm_key}"
        try:
            await jira.add_comment(
                jira_key,
                f"Linked to JSM service-desk ticket {jsm_key}: {jsm_url}",
            )
            logger.info("  ✓ Comment added to Jira %s", jira_key)
        except Exception as exc:
            logger.warning("  ✗ Jira comment failed: %s", exc)

        # 3. Comment on JSM ticket pointing to Jira
        jira_url = req.jira_ticket_url or f"{settings.JIRA_BASE_URL}/browse/{jira_key}"
        try:
            from app.services.jsm_service import JsmService
            jsm = JsmService()
            await jsm.add_comment(
                jsm_key,
                f"Implementation ticket: {jira_key} — {jira_url}",
                public=True,
            )
            logger.info("  ✓ Comment added to JSM %s", jsm_key)
        except Exception as exc:
            logger.warning("  ✗ JSM comment failed: %s", exc)

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
