"""Jira Service Management (JSM) integration.

Creates and updates a customer-facing service-desk ticket for every Blink Relay
request. The ticket mirrors the request lifecycle: it is created on submission,
receives a comment for every thread message and status change, and transitions
to Resolved when the linked dev Jira ticket is marked Done (or when the
request is rejected).

When ``settings.JSM_MOCK`` is true the service returns deterministic fake data
without making any HTTP calls — used for local development and tests.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class JsmServiceError(Exception):
    """Raised when JSM API returns a non-recoverable error."""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout))


def _mock_ticket_key(seed: str) -> str:
    """Deterministic mock JSM ticket key for a given input — useful in tests."""
    digest = hashlib.sha1(seed.encode()).hexdigest()[:6].upper()
    return f"{settings.JSM_PROJECT_KEY}-{digest}"


def _mock_comment_id(seed: str) -> str:
    return hashlib.sha1(f"comment:{seed}".encode()).hexdigest()[:12]


class JsmService:
    """Wrapper around Jira Service Management REST API.

    Honours ``settings.JSM_MOCK`` — when set, every method short-circuits and
    returns deterministic fake data without touching the network. The mock
    behaviour mirrors the shape and key set of the real API responses, so call
    sites and tests behave identically.
    """

    def __init__(self) -> None:
        token = base64.b64encode(
            f"{settings.JIRA_EMAIL}:{settings.JIRA_API_TOKEN}".encode()
        ).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        base = settings.JSM_BASE_URL or settings.JIRA_BASE_URL
        self._base = base.rstrip("/")
        self._mock = settings.JSM_MOCK
        self._service_desk_id = settings.JSM_SERVICE_DESK_ID
        self._request_type_id = settings.JSM_REQUEST_TYPE_ID

        # In local dev, auto-fall-back to mock mode if JSM isn't configured.
        # Avoids breaking submissions when developers haven't set up JSM creds.
        # Production/staging still raise loudly so misconfiguration is visible.
        if (
            not self._mock
            and settings.is_local
            and not self._service_desk_id
        ):
            logger.warning(
                "JSM_SERVICE_DESK_ID/JSM_REQUEST_TYPE_ID not set in local env "
                "— auto-enabling JSM_MOCK so submissions don't fail. "
                "Set JSM_MOCK=true in .env to silence this warning."
            )
            self._mock = True

    # ── Create ticket ─────────────────────────────────────────────────────────

    async def create_request(
        self,
        *,
        summary: str,
        description: str,
        reporter_email: str,
        priority: Optional[str] = None,
        reference_id: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> dict:
        """Create a JSM customer request and return ``{key, url, id}``."""
        if self._mock:
            seed = reference_id or summary
            key = _mock_ticket_key(seed)
            url = f"{self._base}/servicedesk/customer/portal/{self._service_desk_id or '1'}/{key}"
            logger.info("JSM_MOCK: created request %s", key)
            return {"key": key, "url": url, "id": key, "mock": True}

        if not self._service_desk_id or not self._request_type_id:
            raise JsmServiceError(
                "JSM_SERVICE_DESK_ID and JSM_REQUEST_TYPE_ID must be set to call live JSM API"
            )

        payload = {
            "serviceDeskId": self._service_desk_id,
            "requestTypeId": self._request_type_id,
            "raiseOnBehalfOf": reporter_email,
            "requestFieldValues": {
                "summary": summary,
                "description": description,
                **( {"priority": {"name": priority}} if priority else {} ),
                **( {"assignee": {"accountId": settings.JIRA_DEFAULT_ASSIGNEE_ACCOUNT_ID}}
                    if settings.JIRA_DEFAULT_ASSIGNEE_ACCOUNT_ID else {} ),
            },
        }
        return await self._post_request(payload)

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _post_request(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base}/rest/servicedeskapi/request",
                json=payload,
                headers=self._headers,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JsmServiceError(
                    f"JSM API error {exc.response.status_code}: {exc.response.text}"
                ) from exc
            data = resp.json()
            key = data["issueKey"]
            return {
                "key": key,
                "url": f"{self._base}/servicedesk/customer/portal/{self._service_desk_id}/{key}",
                "id": data.get("issueId", key),
            }

    # ── Comments ──────────────────────────────────────────────────────────────

    async def add_comment(
        self,
        ticket_key: str,
        body: str,
        *,
        public: bool = True,
    ) -> dict:
        """Post a comment on a JSM ticket.

        Public comments are visible to the requestor; non-public ("internal")
        comments are only visible to agents on the service desk.
        """
        if self._mock:
            cid = _mock_comment_id(f"{ticket_key}:{body[:40]}")
            logger.info("JSM_MOCK: added comment %s on %s (public=%s)", cid, ticket_key, public)
            return {"id": cid, "ticket_key": ticket_key, "public": public, "mock": True}

        return await self._post_comment(ticket_key, body, public)

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _post_comment(self, ticket_key: str, body: str, public: bool) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base}/rest/servicedeskapi/request/{ticket_key}/comment",
                json={"body": body, "public": public},
                headers=self._headers,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JsmServiceError(
                    f"JSM API error {exc.response.status_code}: {exc.response.text}"
                ) from exc
            data = resp.json()
            return {"id": str(data["id"]), "ticket_key": ticket_key, "public": public}

    # ── Transition / close ────────────────────────────────────────────────────

    async def transition(
        self,
        ticket_key: str,
        transition_name: str,
        comment: Optional[str] = None,
    ) -> dict:
        """Transition a JSM ticket to a new status by transition name."""
        if self._mock:
            logger.info("JSM_MOCK: transitioned %s via '%s'", ticket_key, transition_name)
            return {"ticket_key": ticket_key, "transition": transition_name, "mock": True}

        # Look up the transition ID by name, then POST it
        async with httpx.AsyncClient(timeout=30) as client:
            tlist = await client.get(
                f"{self._base}/rest/api/3/issue/{ticket_key}/transitions",
                headers=self._headers,
            )
            tlist.raise_for_status()
            transitions = tlist.json().get("transitions", [])
            transition_id = next(
                (t["id"] for t in transitions if t["name"].lower() == transition_name.lower()),
                None,
            )
            if not transition_id:
                raise JsmServiceError(
                    f"Transition '{transition_name}' not available on {ticket_key}"
                )

            payload: dict = {"transition": {"id": transition_id}}
            if comment:
                payload["update"] = {"comment": [{"add": {"body": comment}}]}

            resp = await client.post(
                f"{self._base}/rest/api/3/issue/{ticket_key}/transitions",
                json=payload,
                headers=self._headers,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JsmServiceError(
                    f"JSM API error {exc.response.status_code}: {exc.response.text}"
                ) from exc
            return {"ticket_key": ticket_key, "transition": transition_name}

    async def resolve(self, ticket_key: str, resolution_comment: str) -> dict:
        """Convenience: post a comment and transition the ticket to Resolved."""
        return await self.transition(
            ticket_key,
            settings.JSM_RESOLVE_TRANSITION,
            comment=resolution_comment,
        )

    async def get_request(self, ticket_key: str) -> dict:
        """Read JSM ticket — used for verifying integration during tests."""
        if self._mock:
            return {
                "key": ticket_key,
                "currentStatus": {"status": "Open"},
                "mock": True,
            }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base}/rest/servicedeskapi/request/{ticket_key}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()
