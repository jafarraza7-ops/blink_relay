"""
One-off script: create JSM tickets for all requests that don't have one yet.

Queries every request where jsm_ticket_key IS NULL and calls
task_create_jsm_ticket for each one (same task used at submission time).
Safe to run multiple times — task_create_jsm_ticket skips requests that
already have a JSM ticket.

Usage (from backend/ directory, with venv active):
    python backfill_jsm_tickets.py [--dry-run]
"""
from __future__ import annotations

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DRY_RUN = "--dry-run" in sys.argv


async def main() -> None:
    from sqlalchemy import select

    from app.core.database import db_session
    from app.models.request import Request

    async with db_session() as db:
        result = await db.execute(
            select(Request).where(Request.jsm_ticket_key.is_(None))
        )
        requests = result.scalars().all()

    if not requests:
        logger.info("All requests already have JSM tickets — nothing to do.")
        return

    logger.info("Found %d request(s) without a JSM ticket.", len(requests))
    if DRY_RUN:
        for req in requests:
            logger.info("  [dry-run] Would create JSM ticket for %s (%s)", req.reference_id or req.id, req.title)
        return

    from app.workers.tasks import task_create_jsm_ticket

    ok = 0
    skipped = 0
    failed = 0

    for req in requests:
        ref = req.reference_id or str(req.id)
        logger.info("Creating JSM ticket for %s — %s", ref, req.title)
        try:
            result = task_create_jsm_ticket.delay(str(req.id))
            # In eager (sync) mode the result is returned directly; in async
            # Celery mode we just fire-and-forget.
            if isinstance(result, dict):
                if result.get("skipped"):
                    logger.info("  skipped (already exists or JSM not configured)")
                    skipped += 1
                else:
                    logger.info("  created: %s", result.get("key"))
                    ok += 1
            else:
                logger.info("  queued (task id: %s)", getattr(result, 'id', '?'))
                ok += 1
        except Exception as exc:
            logger.error("  FAILED for %s: %s", ref, exc)
            failed += 1

    logger.info("Done. created=%d  skipped=%d  failed=%d", ok, skipped, failed)


if __name__ == "__main__":
    asyncio.run(main())
