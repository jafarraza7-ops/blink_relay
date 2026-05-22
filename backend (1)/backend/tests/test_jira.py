from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.jira_service import (
    JiraService,
    JiraServiceError,
    _build_adf_description,
)


def test_build_adf_description_structure():
    adf = _build_adf_description(
        business_problem="Payments are failing",
        affected_area="Checkout flow",
        submitter_name="Jane Doe",
        submitter_email="jane@example.com",
        reference_id="BLR-2026-0001",
    )
    assert adf["type"] == "doc"
    assert adf["version"] == 1
    assert isinstance(adf["content"], list)
    assert len(adf["content"]) >= 4


def test_build_adf_with_optional_fields():
    adf = _build_adf_description(
        business_problem="Problem",
        affected_area="Area",
        submitter_name="Jane",
        submitter_email="jane@test.com",
        reference_id=None,
        expected_outcome="Better UX",
        steps_to_reproduce="1. Open app",
        additional_context="See ticket ABC-123",
    )
    content_texts = [
        c["content"][0]["text"]
        for c in adf["content"]
        if c.get("type") == "paragraph"
    ]
    assert any("Better UX" in t for t in content_texts)
    assert any("1. Open app" in t for t in content_texts)
    assert any("ABC-123" in t for t in content_texts)


@pytest.mark.asyncio
async def test_create_epic_success():
    svc = JiraService.__new__(JiraService)
    svc._headers = {}
    svc._base = "https://example.atlassian.net"

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"key": "CHG-42", "id": "10042"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_class.return_value = mock_client

        result = await svc.create_epic("CHG", "Test Epic", {"type": "doc", "version": 1, "content": []})

    assert result["key"] == "CHG-42"
    assert "CHG-42" in result["url"]


@pytest.mark.asyncio
async def test_create_ticket_defect_uses_bug():
    svc = JiraService.__new__(JiraService)
    svc._headers = {}
    svc._base = "https://example.atlassian.net"

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"key": "DRV-7", "id": "10007"}

    captured_payload = {}

    async def fake_post(url, json, headers):
        captured_payload.update(json)
        return mock_resp

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_class.return_value = mock_client

        result = await svc.create_ticket(
            project_key="DRV",
            title="Bug report",
            description="Something broke",
            request_type="Defect",
        )

    assert result["key"] == "DRV-7"
    assert captured_payload["fields"]["issuetype"]["name"] == "Bug"


@pytest.mark.asyncio
async def test_jira_service_error_on_4xx():
    import httpx

    svc = JiraService.__new__(JiraService)
    svc._headers = {}
    svc._base = "https://example.atlassian.net"

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Bad Request"
    http_error = httpx.HTTPStatusError("400", request=MagicMock(), response=mock_resp)
    mock_resp.raise_for_status = MagicMock(side_effect=http_error)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_class.return_value = mock_client

        with pytest.raises(JiraServiceError):
            await svc.create_epic("BAD", "title", {"type": "doc", "version": 1, "content": []})


def test_verify_webhook_signature_valid():
    import hashlib
    import hmac

    secret = "my-secret"
    body = b'{"event":"test"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert JiraService.verify_webhook_signature(body, sig, secret) is True


def test_verify_webhook_signature_invalid():
    assert JiraService.verify_webhook_signature(b"body", "sha256=bad", "secret") is False


def test_verify_webhook_signature_no_secret():
    assert JiraService.verify_webhook_signature(b"body", "sha256=anything", "") is True
