"""Escalation detection and notification service."""
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import Request, RequestStatus


async def get_escalated_requests(db: AsyncSession, days_threshold: int = 7) -> list[Request]:
    """Find requests in AwaitingInfo status for >N days.

    Args:
        db: Database session
        days_threshold: Number of days without status change to consider escalated

    Returns:
        List of escalated requests ordered by days waiting (oldest first)
    """
    cutoff_time = datetime.utcnow() - timedelta(days=days_threshold)

    result = await db.execute(
        select(Request)
        .where(Request.status == RequestStatus.AWAITING_INFO)
        .where(Request.updated_at < cutoff_time)
        .order_by(Request.updated_at.asc())
    )
    return result.scalars().all()


async def get_escalation_summary(db: AsyncSession, days_threshold: int = 7) -> dict:
    """Get escalation statistics.

    Returns dict with:
    - total: number of escalated requests
    - by_pod: dict of pod -> count
    - by_priority: dict of priority -> count
    - oldest_days: how long the oldest one has been waiting
    """
    requests = await get_escalated_requests(db, days_threshold)

    if not requests:
        return {
            "total": 0,
            "by_pod": {},
            "by_priority": {},
            "oldest_days": None,
        }

    from collections import defaultdict
    by_pod = defaultdict(int)
    by_priority = defaultdict(int)

    for req in requests:
        by_pod[req.pod] += 1
        by_priority[req.priority] += 1

    oldest_req = requests[0]
    days_waiting = (datetime.utcnow() - oldest_req.updated_at).days

    return {
        "total": len(requests),
        "by_pod": dict(by_pod),
        "by_priority": dict(by_priority),
        "oldest_days": days_waiting,
        "requests": requests,
    }
