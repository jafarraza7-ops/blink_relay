"""Unit tests for the JSM service.

These tests run entirely in mock mode (``settings.JSM_MOCK=true`` from the test
env) — no HTTP calls are made. The service returns deterministic fake data.
For the live-API path, a small subset of tests use ``patch`` against
``httpx.AsyncClient`` to verify the request payload shape without networking.
"""
from __future__ import annotations

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import get_settings
from app.services.jsm_service import (
    JsmService,
    JsmServiceError,
    _mock_comment_id,
    _mock_ticket_key,
)


# ── Mock-mode behaviour ───────────────────────────────────────────────────────

def test_mock_ticket_key_is_deterministic():
    """Same input → same fake key, so tests can assert on specific values."""
    a = _mock_ticket_key("BLR-2026-0001")
    b = _mock_ticket_key("BLR-2026-0001")
    c = _mock_ticket_key("different")
    assert a == b
    assert a != c
    assert a.startswith(get_settings().JSM_PROJECT_KEY + "-")


def test_mock_comment_id_is_deterministic():
    a = _mock_comment_id("BLR-X-some text")
    b = _mock_comment_id("BLR-X-some text")
    assert a == b
    assert len(a) == 12


@pytest.mark.asyncio
async def test_create_request_in_mock_mode_returns_fake_ticket():
    svc = JsmService()
    result = await svc.create_request(
        summary="A new request",
        description="Some description",
        reporter_email="user@blink.com",
        reference_id="BLR-2026-0123",
    )
    assert result["mock"] is True
    assert result["key"].startswith("BLR-")
    assert "servicedesk/customer/portal" in result["url"]
    # Deterministic — second call with same reference_id returns same key
    repeat = await svc.create_request(
        summary="A new request",
        description="Some description",
        reporter_email="user@blink.com",
        reference_id="BLR-2026-0123",
    )
    assert repeat["key"] == result["key"]


@pytest.mark.asyncio
async def test_add_comment_in_mock_mode():
    svc = JsmService()
    result = await svc.add_comment("BLR-ABCDEF", "A test comment", public=True)
    assert result["mock"] is True
    assert result["ticket_key"] == "BLR-ABCDEF"
    assert result["public"] is True
    assert "id" in result


@pytest.mark.asyncio
async def test_add_internal_comment_in_mock_mode():
    svc = JsmService()
    result = await svc.add_comment("BLR-ABCDEF", "internal note", public=False)
    assert result["public"] is False


@pytest.mark.asyncio
async def test_resolve_in_mock_mode_returns_transition_marker():
    svc = JsmService()
    result = await svc.resolve("BLR-ABCDEF", "Resolved during smoke test")
    assert result["mock"] is True
    assert result["ticket_key"] == "BLR-ABCDEF"
    assert result["transition"]


@pytest.mark.asyncio
async def test_get_request_in_mock_mode_returns_fake_status():
    svc = JsmService()
    result = await svc.get_request("BLR-ABCDEF")
    assert result["key"] == "BLR-ABCDEF"
    assert result["currentStatus"]["status"]


# ── Live-API contract tests (httpx is patched, no network) ────────────────────

@pytest.fixture
def live_jsm_service(monkeypatch):
    """JsmService with JSM_MOCK forced off, so we exercise the live code path."""
    monkeypatch.setattr("app.services.jsm_service.settings.JSM_MOCK", False)
    monkeypatch.setattr("app.services.jsm_service.settings.JSM_SERVICE_DESK_ID", "10")
    monkeypatch.setattr("app.services.jsm_service.settings.JSM_REQUEST_TYPE_ID", "100")
    svc = JsmService.__new__(JsmService)
    svc._headers = {"Authorization": "Basic test"}
    svc._base = "https://example.atlassian.net"
    svc._mock = False
    svc._service_desk_id = "10"
    svc._request_type_id = "100"
    return svc


@pytest.mark.asyncio
async def test_create_request_posts_to_servicedeskapi(live_jsm_service):
    captured = {}

    async def fake_post(url, json, headers):
        captured["url"] = url
        captured["json"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"issueKey": "BLR-42", "issueId": "10042"}
        return resp

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_class.return_value = mock_client

        result = await live_jsm_service.create_request(
            summary="Test",
            description="A description",
            reporter_email="user@blink.com",
        )

    assert result["key"] == "BLR-42"
    assert "/rest/servicedeskapi/request" in captured["url"]
    body = captured["json"]
    assert body["serviceDeskId"] == "10"
    assert body["requestTypeId"] == "100"
    assert body["raiseOnBehalfOf"] == "user@blink.com"
    assert body["requestFieldValues"]["summary"] == "Test"


@pytest.mark.asyncio
async def test_create_request_raises_when_service_desk_id_missing(monkeypatch):
    """Live mode requires JSM_SERVICE_DESK_ID and JSM_REQUEST_TYPE_ID."""
    monkeypatch.setattr("app.services.jsm_service.settings.JSM_MOCK", False)
    svc = JsmService.__new__(JsmService)
    svc._mock = False
    svc._service_desk_id = ""
    svc._request_type_id = ""
    svc._headers = {}
    svc._base = "https://example.atlassian.net"

    with pytest.raises(JsmServiceError, match="JSM_SERVICE_DESK_ID"):
        await svc.create_request(
            summary="x", description="y", reporter_email="u@e.com"
        )


@pytest.mark.asyncio
async def test_add_comment_posts_correct_payload(live_jsm_service):
    captured = {}

    async def fake_post(url, json, headers):
        captured["url"] = url
        captured["json"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": 9001}
        return resp

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_class.return_value = mock_client

        result = await live_jsm_service.add_comment("BLR-42", "hello world", public=True)

    assert result["id"] == "9001"
    assert "/rest/servicedeskapi/request/BLR-42/comment" in captured["url"]
    assert captured["json"] == {"body": "hello world", "public": True}


@pytest.mark.asyncio
async def test_jsm_4xx_raises_service_error(live_jsm_service):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Bad Request"
    err = httpx.HTTPStatusError("400", request=MagicMock(), response=mock_resp)
    mock_resp.raise_for_status = MagicMock(side_effect=err)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_class.return_value = mock_client

        with pytest.raises(JsmServiceError, match="400"):
            await live_jsm_service.create_request(
                summary="x", description="y", reporter_email="u@e.com"
            )


@pytest.mark.asyncio
async def test_transition_looks_up_id_then_posts(live_jsm_service):
    """transition() must first GET available transitions and find the matching id."""
    posted = {}
    transition_lookup_response = MagicMock()
    transition_lookup_response.raise_for_status = MagicMock()
    transition_lookup_response.json.return_value = {
        "transitions": [
            {"id": "11", "name": "In Progress"},
            {"id": "31", "name": "Resolve"},
        ]
    }

    transition_post_response = MagicMock()
    transition_post_response.raise_for_status = MagicMock()
    transition_post_response.json.return_value = {}

    async def fake_get(url, headers):
        return transition_lookup_response

    async def fake_post(url, json, headers):
        posted["url"] = url
        posted["json"] = json
        return transition_post_response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get
        mock_client.post = fake_post
        mock_client_class.return_value = mock_client

        result = await live_jsm_service.transition(
            "BLR-42", "Resolve", comment="All done"
        )

    assert result["transition"] == "Resolve"
    assert posted["json"]["transition"] == {"id": "31"}
    # Comment is bundled into the transition payload
    assert posted["json"]["update"]["comment"][0]["add"]["body"] == "All done"


@pytest.mark.asyncio
async def test_transition_unknown_name_raises(live_jsm_service):
    transition_lookup_response = MagicMock()
    transition_lookup_response.raise_for_status = MagicMock()
    transition_lookup_response.json.return_value = {"transitions": []}

    async def fake_get(url, headers):
        return transition_lookup_response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get
        mock_client_class.return_value = mock_client

        with pytest.raises(JsmServiceError, match="not available"):
            await live_jsm_service.transition("BLR-42", "Bogus")
