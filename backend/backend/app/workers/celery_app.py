from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "blink_relay",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks", "app.workers.reminder_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,           # only ack after successful execution
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # fair dispatch — don't pre-fetch more than 1 task
    task_routes={
        "app.workers.tasks.task_create_jira_ticket": {"queue": "jira"},
        "app.workers.tasks.task_send_status_notification": {"queue": "notifications"},
        "app.workers.tasks.task_send_email": {"queue": "notifications"},
        "app.workers.reminder_tasks.task_send_pending_request_reminder": {"queue": "reminders"},
    },
    beat_schedule={
        # Send reminders to PMs about requests pending 72+ hours.
        # Runs every day at 9:00 AM UTC. PMs receive at most one reminder per request per day.
        "send-pending-request-reminder-daily": {
            "task": "app.workers.reminder_tasks.task_send_pending_request_reminder",
            "schedule": crontab(hour=9, minute=0),
        },
        # Send escalation digest: requests in AwaitingInfo status for >7 days.
        # Runs every day at 9:30 AM UTC to follow the reminder digest.
        "send-escalation-digest-daily": {
            "task": "app.workers.tasks.task_send_escalation_digest",
            "schedule": crontab(hour=9, minute=30),
        },
    },
    # Eager mode: tasks run inline (no broker needed). Used for local smoke testing.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=settings.CELERY_TASK_ALWAYS_EAGER,
)
