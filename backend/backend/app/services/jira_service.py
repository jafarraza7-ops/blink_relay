from __future__ import annotations

import base64
import hashlib
import hmac
import logging

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


_PRIORITY_MAP: dict[str, str] = {
    "Critical": "P0 - CRITICAL",
    "High": "P1 - HIGH",
    "Medium": "P2 - MEDIUM",
    "Low": "P3 - LOW",
}


def map_priority(priority: str) -> str:
    return _PRIORITY_MAP.get(priority, "P2 - MEDIUM")


class JiraServiceError(Exception):
    pass


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


def _adf_paragraph(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _adf_heading(text: str, level: int = 3) -> dict:
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [{"type": "text", "text": text}],
    }


def _build_adf_description(
    business_problem: str,
    affected_area: str,
    submitter_name: str,
    submitter_email: str,
    reference_id: str | None,
    region: str | None = None,
    expected_outcome: str | None = None,
    steps_to_reproduce: str | None = None,
    additional_context: str | None = None,
    approver_name: str | None = None,
    approver_email: str | None = None,
) -> dict:
    content = [
        _adf_heading("Business Problem"),
        _adf_paragraph(business_problem),
        _adf_heading("Affected Area"),
        _adf_paragraph(affected_area),
    ]
    if region:
        content += [_adf_heading("Region"), _adf_paragraph(region)]
    if expected_outcome:
        content += [_adf_heading("Expected Outcome"), _adf_paragraph(expected_outcome)]
    if steps_to_reproduce:
        content += [_adf_heading("Steps to Reproduce"), _adf_paragraph(steps_to_reproduce)]
    if additional_context:
        content += [_adf_heading("Additional Context"), _adf_paragraph(additional_context)]
    metadata = (
        f"Submitted by: {submitter_name} ({submitter_email})\n"
        f"Blink Relay ID: {reference_id or 'N/A'}"
    )
    if approver_name:
        approver_line = f"Approved by: {approver_name}"
        if approver_email:
            approver_line += f" ({approver_email})"
        metadata += f"\n{approver_line}"
    content += [_adf_heading("Metadata"), _adf_paragraph(metadata)]
    return {"type": "doc", "version": 1, "content": content}


class JiraService:
    def __init__(self) -> None:
        token = base64.b64encode(
            f"{settings.JIRA_EMAIL}:{settings.JIRA_API_TOKEN}".encode()
        ).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._base = settings.JIRA_BASE_URL.rstrip("/")

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _post_issue(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base}/rest/api/3/issue",
                json=payload,
                headers=self._headers,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JiraServiceError(
                    f"Jira API error {exc.response.status_code}: {exc.response.text}"
                ) from exc
            data = resp.json()
            return {
                "key": data["key"],
                "url": f"{self._base}/browse/{data['key']}",
                "id": data["id"],
            }

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def add_comment(self, ticket_key: str, body: str) -> dict:
        """Add a plain-text comment to a Jira issue."""
        adf_body = {
            "type": "doc",
            "version": 1,
            "content": [_adf_paragraph(body)],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base}/rest/api/3/issue/{ticket_key}/comment",
                json={"body": adf_body},
                headers=self._headers,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JiraServiceError(
                    f"Jira API error {exc.response.status_code}: {exc.response.text}"
                ) from exc
            data = resp.json()
            return {"id": str(data["id"]), "ticket_key": ticket_key}

    def _assignee_field(self) -> dict | None:
        account_id = settings.JIRA_DEFAULT_ASSIGNEE_ACCOUNT_ID
        return {"accountId": account_id} if account_id else None

    async def upload_attachment(
        self, ticket_key: str, filename: str, content_type: str, data: bytes
    ) -> dict:
        """Upload a file attachment to a Jira or JSM issue."""
        headers = {k: v for k, v in self._headers.items() if k != "Content-Type"}
        headers["X-Atlassian-Token"] = "no-check"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base}/rest/api/3/issue/{ticket_key}/attachments",
                headers=headers,
                files={"file": (filename, data, content_type)},
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JiraServiceError(
                    f"Jira attachment error {exc.response.status_code}: {exc.response.text}"
                ) from exc
        logger.info("Attachment '%s' uploaded to %s", filename, ticket_key)
        return {"ticket_key": ticket_key, "filename": filename}

    async def get_account_id_by_email(self, email: str) -> str | None:
        """Return the Jira accountId for the given email, or None if not found."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base}/rest/api/3/user/search",
                    params={"query": email},
                    headers=self._headers,
                )
                if resp.status_code != 200:
                    return None
                for user in resp.json():
                    if user.get("emailAddress", "").lower() == email.lower():
                        return user["accountId"]
        except Exception:
            logger.warning("Failed to look up Jira account for %s", email)
        return None

    def _build_issue_fields(
        self,
        project_key: str,
        title: str,
        description_adf: dict,
        issue_type: str,
        priority: str = "Medium",  # must match a priority name in the Jira project
        labels: list[str] | None = None,
        component: str | None = None,
        assignee_account_id: str | None = None,
    ) -> dict:
        fields: dict = {
            "project": {"key": project_key},
            "summary": title,
            "description": description_adf,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "labels": (labels or []) + ["blink-relay"],
        }
        if component:
            fields["components"] = [{"name": component}]
        assignee = ({"accountId": assignee_account_id} if assignee_account_id else self._assignee_field())
        if assignee:
            fields["assignee"] = assignee
        return fields

    async def create_epic(
        self,
        project_key: str,
        title: str,
        description_adf: dict,
        priority: str = "Medium",
        labels: list[str] | None = None,
        component: str | None = None,
        assignee_account_id: str | None = None,
    ) -> dict:
        fields = self._build_issue_fields(
            project_key, title, description_adf, "Story", priority, labels, component, assignee_account_id
        )
        return await self._post_issue({"fields": fields})

    async def create_bug_ticket(
        self,
        project_key: str,
        title: str,
        description_adf: dict,
        priority: str = "Medium",
        labels: list[str] | None = None,
        component: str | None = None,
        assignee_account_id: str | None = None,
    ) -> dict:
        fields = self._build_issue_fields(
            project_key, title, description_adf, "Bug", priority, labels, component, assignee_account_id
        )
        return await self._post_issue({"fields": fields})

    async def create_ticket(
        self,
        project_key: str,
        title: str,
        description: str,
        request_type: str,
        priority: str = "Medium",
        labels: list[str] | None = None,
        submitter_name: str = "",
        submitter_email: str = "",
        reference_id: str | None = None,
        affected_area: str = "",
        region: str | None = None,
        expected_outcome: str | None = None,
        steps_to_reproduce: str | None = None,
        additional_context: str | None = None,
        component: str | None = None,
        assignee_account_id: str | None = None,
        approver_name: str | None = None,
        approver_email: str | None = None,
    ) -> dict:
        adf = _build_adf_description(
            business_problem=description,
            affected_area=affected_area,
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            reference_id=reference_id,
            region=region,
            expected_outcome=expected_outcome,
            steps_to_reproduce=steps_to_reproduce,
            additional_context=additional_context,
            approver_name=approver_name,
            approver_email=approver_email,
        )
        _priority_map = {
            "CRITICAL": "P0 - CRITICAL",
            "HIGH": "P1 - HIGH",
            "MEDIUM": "P2 - MEDIUM",
            "LOW": "P3 - LOW",
        }
        jira_priority = _priority_map.get(priority.upper(), "P2 - MEDIUM")
        if request_type == "Defect":
            return await self.create_bug_ticket(project_key, title, adf, jira_priority, labels, component, assignee_account_id)
        return await self.create_epic(project_key, title, adf, jira_priority, labels, component, assignee_account_id)

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def get_ticket(self, ticket_key: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base}/rest/api/3/issue/{ticket_key}",
                headers=self._headers,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JiraServiceError(
                    f"Jira API error {exc.response.status_code}: {exc.response.text}"
                ) from exc
            return resp.json()

    async def link_issues(
        self,
        inward_key: str,
        outward_key: str,
        link_type: str = "Relates",
    ) -> dict:
        """Create a formal issue link between two Jira/JSM issues.

        The link appears in the 'Issue links' section of both tickets.
        ``link_type`` must match a link-type name configured in the Jira instance
        (e.g. 'Relates', 'Blocks', 'Cloners').
        """
        payload = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base}/rest/api/3/issueLink",
                json=payload,
                headers=self._headers,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JiraServiceError(
                    f"Jira link error {exc.response.status_code}: {exc.response.text}"
                ) from exc
        logger.info("Linked %s ↔ %s (%s)", inward_key, outward_key, link_type)
        return {"inward": inward_key, "outward": outward_key, "type": link_type}

    @staticmethod
    def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
        if not secret:
            return True
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)
