"""digest_service.py — Generate weekly summary digests for stakeholders."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import Request, RequestStatus, Message, MessageType


async def get_weekly_digest_data(db: AsyncSession) -> dict:
    """Compile weekly digest statistics and trending issues.

    Returns a dict with:
      - total: total requests in system
      - this_week: requests created this week
      - by_status: breakdown by status
      - by_pod: breakdown by pod
      - overdue: requests pending >7 days
      - trending: top 5 most active requests
      - completed: requests completed this week
      - stats: key metrics
    """
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Total requests
    total = await db.scalar(select(func.count()).select_from(Request))

    # This week's new requests
    this_week = await db.scalar(
        select(func.count()).select_from(Request)
        .where(Request.created_at >= week_ago)
    )

    # By status
    status_result = await db.execute(
        select(Request.status, func.count())
        .select_from(Request)
        .group_by(Request.status)
    )
    by_status = {status: count for status, count in status_result.all()}

    # By pod
    pod_result = await db.execute(
        select(Request.pod, func.count())
        .select_from(Request)
        .group_by(Request.pod)
    )
    by_pod = {str(pod) if pod else "Unknown": count for pod, count in pod_result.all()}

    # Overdue requests (pending >7 days in Submitted/InReview)
    overdue = await db.scalar(
        select(func.count()).select_from(Request)
        .where(
            and_(
                Request.status.in_([RequestStatus.SUBMITTED, RequestStatus.IN_REVIEW]),
                Request.created_at < week_ago,
            )
        )
    )

    # Trending: requests with most messages this week
    trending_result = await db.execute(
        select(Request.reference_id, Request.title, func.count(Message.id))
        .select_from(Request)
        .outerjoin(Message, Message.request_id == Request.id)
        .where(Request.created_at >= week_ago)
        .group_by(Request.id, Request.reference_id, Request.title)
        .order_by(func.count(Message.id).desc())
        .limit(5)
    )
    trending = [
        {"reference_id": ref, "title": title, "messages": count}
        for ref, title, count in trending_result.all()
    ]

    # Recently completed
    completed_result = await db.execute(
        select(Request.reference_id, Request.title, Request.updated_at)
        .select_from(Request)
        .where(
            and_(
                Request.status == RequestStatus.COMPLETED,
                Request.updated_at >= week_ago,
            )
        )
        .order_by(Request.updated_at.desc())
        .limit(5)
    )
    completed = [
        {"reference_id": ref, "title": title, "completed_at": updated.strftime("%Y-%m-%d")}
        for ref, title, updated in completed_result.all()
    ]

    # Approved this week
    approved_week = await db.scalar(
        select(func.count()).select_from(Request)
        .where(
            and_(
                Request.status == RequestStatus.APPROVED,
                Request.updated_at >= week_ago,
            )
        )
    )

    return {
        "total": total,
        "this_week": this_week,
        "by_status": by_status,
        "by_pod": by_pod,
        "overdue": overdue,
        "trending": trending,
        "completed": completed,
        "approved_week": approved_week,
        "period": {
            "start": week_ago.strftime("%Y-%m-%d"),
            "end": now.strftime("%Y-%m-%d"),
        },
    }
