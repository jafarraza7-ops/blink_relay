from __future__ import annotations

import uuid
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.request import (
    Pod, Priority, Request, RequestStatus, RequestType, )


def _make_mock_request(status=RequestStatus.APPROVED, pod=Pod.DRIVER):
    req = MagicMock(spec=Request)
    req.id = uuid.uuid4()
    req.title = "Test Request"
    req.request_type = RequestType.FEATURE
    req.pod = pod
    req.priority = Priority.MEDIUM
    req.status = status
    req.business_problem = "Test business problem"
    req.affected_area = "Driver app"
    req.submitter_name = "Test User"
    req.submitter_email = "test@test.com"
    req.reference_id = "BLR-2026-0001"
    req.jira_ticket_key = None
    req.jira_ticket_url = None
    req.rejection_reason = None
    req.rejection_comment = None
    req.expected_outcome = None
    req.steps_to_reproduce = None
    req.additional_context = None
    return req


def _make_db_ctx(mock_req):
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_req)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    @asynccontextmanager
    async def mock_session():
        yield mock_db

    return mock_session


# Task tests are SYNC because Celery's _run() creates its own event loop
# and pytest-asyncio's running loop would conflict.

def test_route_request_to_pod_already_known():
    from app.workers.tasks import route_request_to_pod

    req = _make_mock_request(pod=Pod.DRIVER)

    with patch("app.core.database.task_db_session", _make_db_ctx(req)):
        result = route_request_to_pod(str(req.id))

    assert result["auto_routed"] is False


def test_route_request_to_pod_unknown_routed():
    from app.workers.tasks import route_request_to_pod
    from app.services.pod_routing_service import RoutingResult

    req = _make_mock_request(pod=Pod.UNKNOWN)
    req.title = "Driver mobile app crash"
    req.business_problem = "iOS app crashing on checkout"

    mock_result = RoutingResult(pod=Pod.DRIVER, confidence=0.80, matched_keywords=["driver", "app", "ios"])

    with (
        patch("app.core.database.task_db_session", _make_db_ctx(req)),
        patch("app.services.pod_routing_service.PodRoutingService.route", return_value=mock_result),
    ):
        result = route_request_to_pod(str(req.id))

    assert result["auto_routed"] is True
    assert result["pod"] == "Driver"


def test_route_request_to_pod_not_found():
    from app.workers.tasks import route_request_to_pod

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_session():
        yield mock_db

    with patch("app.core.database.task_db_session", mock_session):
        result = route_request_to_pod(str(uuid.uuid4()))

    assert result == {}


def test_task_create_jira_ticket_success():
    from app.workers.tasks import task_create_jira_ticket

    req = _make_mock_request(status=RequestStatus.APPROVED)
    ticket = {"key": "DRV-42", "url": "https://jira.example.com/browse/DRV-42", "id": "10042"}

    with (
        patch("app.core.database.task_db_session", _make_db_ctx(req)),
        patch("app.services.jira_service.JiraService.create_ticket", AsyncMock(return_value=ticket)),
        patch("app.services.pod_routing_service.PodRoutingService.get_jira_project", return_value="DRV"),
    ):
        result = task_create_jira_ticket(str(req.id))

    assert result["key"] == "DRV-42"
    assert req.jira_ticket_key == "DRV-42"


def test_task_create_jira_ticket_not_found():
    from app.workers.tasks import task_create_jira_ticket

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_session():
        yield mock_db

    with patch("app.core.database.task_db_session", mock_session):
        result = task_create_jira_ticket(str(uuid.uuid4()))

    assert result == {}


def test_task_send_status_notification_submitted():
    from app.workers.tasks import task_send_status_notification

    req = _make_mock_request(status=RequestStatus.SUBMITTED)

    with (
        patch("app.core.database.task_db_session", _make_db_ctx(req)),
        patch("app.services.notification_service.NotificationService.notify_submitted", AsyncMock()),
        patch("app.services.notification_service.NotificationService.send_teams_notification", AsyncMock()),
        patch("app.services.pod_routing_service.PodRoutingService.get_teams_webhook", return_value=""),
    ):
        task_send_status_notification(str(req.id))


def test_task_send_status_notification_approved():
    from app.workers.tasks import task_send_status_notification

    req = _make_mock_request(status=RequestStatus.APPROVED)
    req.jira_ticket_url = "https://jira.example.com/browse/DRV-1"

    with (
        patch("app.core.database.task_db_session", _make_db_ctx(req)),
        patch("app.services.notification_service.NotificationService.notify_approved", AsyncMock()),
        patch("app.services.notification_service.NotificationService.send_teams_notification", AsyncMock()),
        patch("app.services.pod_routing_service.PodRoutingService.get_teams_webhook", return_value=""),
        patch("app.services.email_group_service.get_pm_group_emails", AsyncMock(return_value=(None, []))),
    ):
        task_send_status_notification(str(req.id))


def test_task_send_status_notification_rejected():
    from app.workers.tasks import task_send_status_notification

    req = _make_mock_request(status=RequestStatus.REJECTED)
    req.rejection_reason = "OutOfScope"
    req.rejection_comment = "Not in Q3"

    with (
        patch("app.core.database.task_db_session", _make_db_ctx(req)),
        patch("app.services.notification_service.NotificationService.notify_rejected", AsyncMock()),
        patch("app.services.notification_service.NotificationService.send_teams_notification", AsyncMock()),
        patch("app.services.pod_routing_service.PodRoutingService.get_teams_webhook", return_value=""),
        patch("app.services.email_group_service.get_pm_group_emails", AsyncMock(return_value=(None, []))),
    ):
        task_send_status_notification(str(req.id))


def test_task_send_status_notification_in_review():
    from app.workers.tasks import task_send_status_notification

    req = _make_mock_request(status=RequestStatus.IN_REVIEW)

    with (
        patch("app.core.database.task_db_session", _make_db_ctx(req)),
        patch("app.services.notification_service.NotificationService.notify_status_change", AsyncMock()),
        patch("app.services.notification_service.NotificationService.send_teams_notification", AsyncMock()),
        patch("app.services.pod_routing_service.PodRoutingService.get_teams_webhook", return_value=""),
        patch("app.services.email_group_service.get_pm_group_emails", AsyncMock(return_value=(None, []))),
    ):
        task_send_status_notification(str(req.id))


def test_task_send_status_notification_not_found():
    from app.workers.tasks import task_send_status_notification

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_session():
        yield mock_db

    with patch("app.core.database.task_db_session", mock_session):
        task_send_status_notification(str(uuid.uuid4()))


def test_sync_jira_status_updates():
    from app.workers.tasks import sync_jira_status

    req = _make_mock_request(status=RequestStatus.APPROVED)
    req.jira_ticket_key = "DRV-42"

    jira_data = {"fields": {"status": {"name": "In Progress"}}}

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=req)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    @asynccontextmanager
    async def mock_session():
        yield mock_db

    with (
        patch("app.core.database.task_db_session", mock_session),
        patch("app.services.jira_service.JiraService.get_ticket", AsyncMock(return_value=jira_data)),
    ):
        result = sync_jira_status(str(req.id))

    assert result["synced"] is True
    assert result["new_status"] == "InProgress"


def test_sync_jira_status_no_ticket():
    from app.workers.tasks import sync_jira_status

    req = _make_mock_request(status=RequestStatus.SUBMITTED)
    req.jira_ticket_key = None

    with patch("app.core.database.task_db_session", _make_db_ctx(req)):
        result = sync_jira_status(str(req.id))

    assert result["synced"] is False


def test_task_send_email():
    from app.workers.tasks import task_send_email

    with patch("app.services.notification_service.NotificationService.send_email", AsyncMock()) as mock_send:
        task_send_email("to@test.com", "Subject", "<p>Body</p>")
        mock_send.assert_called_once_with("to@test.com", "Subject", "<p>Body</p>")
