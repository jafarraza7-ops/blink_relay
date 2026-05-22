from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "blink_relay",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
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
    },
    beat_schedule={},
    # Eager mode: tasks run inline (no broker needed). Used for local smoke testing.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=settings.CELERY_TASK_ALWAYS_EAGER,
)
