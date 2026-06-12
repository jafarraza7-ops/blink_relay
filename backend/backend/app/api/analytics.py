"""
analytics.py — PM Dashboard analytics endpoints.

Provides summary metrics, funnel data, pod performance, and escalation
alerts for the PM Summary Dashboard.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import UserClaims, Role, get_current_user
from app.models.request import Request, RequestStatus, Pod

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_pm_or_reviewer(user: UserClaims) -> UserClaims:
    """Ensure user is PM or Pod Reviewer."""
    if not user.roles or not any(
        role in user.roles for role in [Role.PRODUCT_MANAGER, Role.POD_REVIEWER, Role.ADMIN]
    ):
        raise HTTPException(status_code=403, detail="Only PMs can access analytics")
    return user


@router.get("/summary")
async def get_summary(
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get overall request summary metrics."""
    _require_pm_or_reviewer(user)

    total_result = await db.execute(select(func.count()).select_from(Request))
    total = total_result.scalar() or 0

    status_result = await db.execute(
        select(Request.status, func.count())
        .group_by(Request.status)
    )
    status_counts = {status: count for status, count in status_result.fetchall()}

    cycle_time_result = await db.execute(
        select(func.avg(
            func.julianday(Request.updated_at) - func.julianday(Request.created_at)
        )).select_from(Request).where(Request.status.in_([
            RequestStatus.COMPLETED, RequestStatus.CLOSED, RequestStatus.CANCELLED
        ]))
    )
    cycle_time_avg = cycle_time_result.scalar() or 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    week_result = await db.execute(
        select(func.count()).select_from(Request).where(Request.created_at >= week_ago)
    )
    requests_this_week = week_result.scalar() or 0

    return {
        "total": total,
        "by_status": {
            "submitted": status_counts.get(RequestStatus.SUBMITTED, 0),
            "in_review": status_counts.get(RequestStatus.IN_REVIEW, 0),
            "awaiting_info": status_counts.get(RequestStatus.AWAITING_INFO, 0),
            "approved": status_counts.get(RequestStatus.APPROVED, 0),
            "in_progress": status_counts.get(RequestStatus.IN_PROGRESS, 0),
            "completed": status_counts.get(RequestStatus.COMPLETED, 0),
            "rejected": status_counts.get(RequestStatus.REJECTED, 0),
            "cancelled": status_counts.get(RequestStatus.CANCELLED, 0),
            "closed": status_counts.get(RequestStatus.CLOSED, 0),
        },
        "cycle_time_avg_days": round(cycle_time_avg, 1),
        "requests_this_week": requests_this_week,
        "requests_per_week": round(requests_this_week, 1),
    }


@router.get("/flow")
async def get_flow(
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get request flow funnel data."""
    _require_pm_or_reviewer(user)

    statuses = [
        RequestStatus.SUBMITTED,
        RequestStatus.IN_REVIEW,
        RequestStatus.APPROVED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.COMPLETED,
        RequestStatus.REJECTED,
    ]

    funnel = {}
    for i, status in enumerate(statuses):
        result = await db.execute(
            select(func.count()).select_from(Request).where(Request.status == status)
        )
        count = result.scalar() or 0

        if i == 0:
            conversion = 100.0
        else:
            prev_result = await db.execute(
                select(func.count()).select_from(Request).where(Request.status == statuses[i - 1])
            )
            prev_count = prev_result.scalar() or 1
            conversion = round((count / prev_count * 100), 1) if prev_count > 0 else 0.0

        funnel[status.lower()] = {
            "count": count,
            "conversion_percent": conversion,
        }

    return funnel


@router.get("/pod-performance")
async def get_pod_performance(
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get per-pod performance metrics."""
    _require_pm_or_reviewer(user)

    pods = [Pod.CHARGER, Pod.DRIVER, Pod.REVENUE, Pod.DATA, Pod.DEVOPS, Pod.DENALI]
    performance = {}

    for pod in pods:
        total_result = await db.execute(
            select(func.count()).select_from(Request).where(Request.pod == pod)
        )
        total = total_result.scalar() or 0

        if total == 0:
            performance[pod] = {
                "total": 0,
                "completed": 0,
                "completion_percent": 0.0,
                "in_progress": 0,
                "awaiting_action": 0,
                "cycle_time_days": 0.0,
                "velocity_per_week": 0.0,
            }
            continue

        completed_result = await db.execute(
            select(func.count()).select_from(Request).where(
                and_(Request.pod == pod, Request.status.in_([
                    RequestStatus.COMPLETED, RequestStatus.CLOSED
                ]))
            )
        )
        completed = completed_result.scalar() or 0

        in_progress_result = await db.execute(
            select(func.count()).select_from(Request).where(
                and_(Request.pod == pod, Request.status == RequestStatus.IN_PROGRESS)
            )
        )
        in_progress = in_progress_result.scalar() or 0

        awaiting_result = await db.execute(
            select(func.count()).select_from(Request).where(
                and_(Request.pod == pod, Request.status.in_([
                    RequestStatus.AWAITING_INFO, RequestStatus.IN_REVIEW
                ]))
            )
        )
        awaiting = awaiting_result.scalar() or 0

        cycle_result = await db.execute(
            select(func.avg(
                func.julianday(Request.updated_at) - func.julianday(Request.created_at)
            )).select_from(Request).where(
                and_(Request.pod == pod, Request.status.in_([
                    RequestStatus.COMPLETED, RequestStatus.CLOSED
                ]))
            )
        )
        cycle_time = cycle_result.scalar() or 0

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        velocity_result = await db.execute(
            select(func.count()).select_from(Request).where(
                and_(
                    Request.pod == pod,
                    Request.updated_at >= week_ago,
                    Request.status.in_([RequestStatus.COMPLETED, RequestStatus.CLOSED])
                )
            )
        )
        velocity = velocity_result.scalar() or 0

        performance[pod] = {
            "total": total,
            "completed": completed,
            "completion_percent": round((completed / total * 100), 1),
            "in_progress": in_progress,
            "awaiting_action": awaiting,
            "cycle_time_days": round(cycle_time, 1),
            "velocity_per_week": round(velocity, 1),
        }

    return performance


@router.get("/escalations")
async def get_escalations(
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days_threshold: int = 7,
) -> dict:
    """Get escalations: requests stuck longer than threshold."""
    _require_pm_or_reviewer(user)

    threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)

    result = await db.execute(
        select(Request).where(
            and_(
                Request.status.in_([RequestStatus.AWAITING_INFO, RequestStatus.IN_REVIEW]),
                Request.updated_at < threshold_date,
            )
        ).order_by(Request.created_at)
    )
    escalations = result.scalars().all()

    return {
        "total": len(escalations),
        "threshold_days": days_threshold,
        "escalations": [
            {
                "reference_id": req.reference_id or str(req.id),
                "title": req.title,
                "status": req.status,
                "days_stuck": (datetime.now(timezone.utc) - req.updated_at).days,
                "last_updated": req.updated_at.isoformat(),
                "submitter_email": req.submitter_email,
            }
            for req in escalations
        ],
    }


@router.get("/trend")
async def get_trend(
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    weeks: int = 8,
) -> dict:
    """Get weekly request creation trend."""
    _require_pm_or_reviewer(user)

    trend = {}
    for i in range(weeks):
        week_start = datetime.now(timezone.utc) - timedelta(days=(weeks - i) * 7)
        week_end = week_start + timedelta(days=7)

        result = await db.execute(
            select(func.count()).select_from(Request).where(
                and_(Request.created_at >= week_start, Request.created_at < week_end)
            )
        )
        count = result.scalar() or 0
        week_label = f"W{weeks - i}"
        trend[week_label] = count

    return trend


@router.get("/request-aging")
async def get_request_aging(
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get request aging breakdown: fresh, aging, stale by days idle.

    Categories:
    - Fresh: 0-30 days since last update
    - Aging: 30-60 days since last update
    - Stale: 60+ days since last update
    """
    _require_pm_or_reviewer(user)

    now = datetime.now(timezone.utc)
    fresh_threshold = now - timedelta(days=30)
    aging_threshold = now - timedelta(days=60)

    # Count requests in each aging bucket
    fresh_result = await db.execute(
        select(func.count()).select_from(Request).where(
            Request.updated_at >= fresh_threshold
        )
    )
    fresh_count = fresh_result.scalar() or 0

    aging_result = await db.execute(
        select(func.count()).select_from(Request).where(
            and_(
                Request.updated_at >= aging_threshold,
                Request.updated_at < fresh_threshold,
            )
        )
    )
    aging_count = aging_result.scalar() or 0

    stale_result = await db.execute(
        select(func.count()).select_from(Request).where(
            Request.updated_at < aging_threshold
        )
    )
    stale_count = stale_result.scalar() or 0

    # Get top 5 stale requests for detail view
    stale_requests_result = await db.execute(
        select(Request)
        .where(Request.updated_at < aging_threshold)
        .order_by(Request.updated_at.asc())
        .limit(5)
    )
    stale_requests = stale_requests_result.scalars().all()

    return {
        "fresh": {
            "count": fresh_count,
            "label": "0-30 days",
            "days_range": [0, 30],
        },
        "aging": {
            "count": aging_count,
            "label": "30-60 days",
            "days_range": [30, 60],
        },
        "stale": {
            "count": stale_count,
            "label": "60+ days",
            "days_range": [60, 999],
        },
        "stale_requests": [
            {
                "reference_id": req.reference_id or str(req.id),
                "title": req.title,
                "status": req.status,
                "days_idle": (now - (req.updated_at.replace(tzinfo=timezone.utc) if req.updated_at and req.updated_at.tzinfo is None else req.updated_at)).days,
                "pod": req.pod,
            }
            for req in stale_requests
        ],
    }
