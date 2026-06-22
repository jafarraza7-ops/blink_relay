from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notification_service import NotificationService


@pytest.fixture
def svc():
    return NotificationService()


@pytest.mark.asyncio
async def test_send_email_success(svc: NotificationService):
    with patch.object(svc, "_send_smtp", AsyncMock()) as mock_send:
        await svc.send_email("to@test.com", "Subject", "<p>Body</p>")
        mock_send.assert_called_once_with("to@test.com", "Subject", "<p>Body</p>", cc=None)


@pytest.mark.asyncio
async def test_send_email_swallows_errors(svc: NotificationService):
    with patch.object(svc, "_send_smtp", AsyncMock(side_effect=Exception("Network error"))):
        # Should not raise
        await svc.send_email("to@test.com", "Subject", "<p>Body</p>")


@pytest.mark.asyncio
async def test_notify_submitted(svc: NotificationService):
    with patch.object(svc, "send_email", AsyncMock()) as mock_send:
        await svc.notify_submitted("user@test.com", "My Request", "BLR-2026-0001")
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[0] == "user@test.com"
        assert "BLR-2026-0001" in args[1]


@pytest.mark.asyncio
async def test_notify_approved(svc: NotificationService):
    with patch.object(svc, "send_email", AsyncMock()) as mock_send:
        await svc.notify_approved("user@test.com", "My Request", "BLR-2026-0001", "https://jira.example.com/BLR-1")
        mock_send.assert_called_once()
        subject = mock_send.call_args[0][1]
        assert "approved" in subject.lower()


@pytest.mark.asyncio
async def test_notify_rejected(svc: NotificationService):
    with patch.object(svc, "send_email", AsyncMock()) as mock_send:
        await svc.notify_rejected("user@test.com", "My Request", "BLR-2026-0001", "OutOfScope", "Not this quarter.")
        mock_send.assert_called_once()
        body_html = mock_send.call_args[0][2]
        assert "OutOfScope" in body_html
        assert "Not this quarter." in body_html


@pytest.mark.asyncio
async def test_notify_awaiting_info(svc: NotificationService):
    with patch.object(svc, "send_email", AsyncMock()) as mock_send:
        await svc.notify_awaiting_info("user@test.com", "My Request", "BLR-2026-0001", "What is the expected behaviour?")
        mock_send.assert_called_once()
        body_html = mock_send.call_args[0][2]
        assert "What is the expected behaviour?" in body_html


@pytest.mark.asyncio
async def test_notify_status_change(svc: NotificationService):
    with patch.object(svc, "send_email", AsyncMock()) as mock_send:
        await svc.notify_status_change("user@test.com", "My Request", "BLR-2026-0001", "InReview")
        mock_send.assert_called_once()
        subject = mock_send.call_args[0][1]
        assert "Status Updated" in subject


@pytest.mark.asyncio
async def test_teams_notification_no_webhook(svc: NotificationService):
    # No URL → should silently skip
    await svc.send_teams_notification("", {"text": "test"})


@pytest.mark.asyncio
async def test_teams_notification_success(svc: NotificationService):
    with patch("httpx.AsyncClient") as mock_cls:
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_http

        await svc.send_teams_notification("https://teams.example.com/hook", {"text": "hello"})
        mock_http.post.assert_called_once()


@pytest.mark.asyncio
async def test_teams_notification_swallows_errors(svc: NotificationService):
    with patch("httpx.AsyncClient", side_effect=Exception("Connection error")):
        await svc.send_teams_notification("https://teams.example.com/hook", {"text": "test"})
