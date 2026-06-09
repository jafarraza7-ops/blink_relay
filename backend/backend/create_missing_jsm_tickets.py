#!/usr/bin/env python3
"""Create JSM tickets for all requests that don't have one yet."""
import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import AsyncSessionLocal
from app.models.request import Request
from app.workers.tasks import task_create_jsm_ticket
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


async def create_missing_jsm_tickets():
    """Find all requests without JSM tickets and queue ticket creation."""
    async with AsyncSessionLocal() as db:
        # Fetch all requests without JSM tickets
        result = await db.execute(
            select(Request).where(Request.jsm_ticket_key.is_(None))
        )
        requests_without_jsm = result.scalars().all()

        if not requests_without_jsm:
            logger.info("✅ All requests already have JSM tickets!")
            return

        logger.info(f"Found {len(requests_without_jsm)} requests without JSM tickets")
        logger.info("\nRequests that need JSM tickets:")

        for req in requests_without_jsm:
            logger.info(f"  - {req.reference_id}: {req.title} (Status: {req.status})")

        # Queue JSM ticket creation for each
        logger.info(f"\n🚀 Queuing JSM ticket creation for {len(requests_without_jsm)} requests...")

        for req in requests_without_jsm:
            try:
                task_create_jsm_ticket.delay(str(req.id))
                logger.info(f"  ✓ Queued: {req.reference_id}")
            except Exception as e:
                logger.error(f"  ✗ Failed to queue {req.reference_id}: {e}")

        logger.info(f"\n✅ All {len(requests_without_jsm)} JSM ticket creation tasks queued!")


if __name__ == "__main__":
    asyncio.run(create_missing_jsm_tickets())
