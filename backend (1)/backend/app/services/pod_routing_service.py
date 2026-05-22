from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.models.request import Pod, RequestType

settings = get_settings()

_KEYWORDS: dict[Pod, list[str]] = {
    Pod.CHARGER: [
        "charger", "charging", "evse", "firmware", "hardware", "connector",
        "ocpp", "station", "outlet", "plug", "power", "voltage", "network",
        "chargepoint", "level 2", "dcfc", "dc fast",
    ],
    Pod.DRIVER: [
        "driver", "app", "mobile", "ios", "android", "checkout", "session",
        "start charge", "stop charge", "rfid", "card", "user experience",
        "ux", "notification", "push", "account", "profile",
    ],
    Pod.REVENUE: [
        "billing", "payment", "invoice", "revenue", "stripe", "pricing",
        "subscription", "charge fee", "refund", "transaction", "credit",
        "debit", "wallet", "cost", "rate", "tariff",
    ],
    Pod.DATA: [
        "data", "analytics", "report", "dashboard", "metric", "kpi",
        "pipeline", "warehouse", "snowflake", "dbt", "etl", "insight",
        "export", "csv", "chart", "graph", "trend",
    ],
    Pod.DEVOPS: [
        "deploy", "deployment", "ci/cd", "pipeline", "kubernetes", "k8s",
        "docker", "infrastructure", "terraform", "azure", "devops",
        "monitoring", "alert", "logging", "observability", "scale",
        "performance", "latency", "uptime", "sla",
    ],
    Pod.DENALI: [
        "enterprise", "fleet", "b2b", "commercial", "workplace", "depot",
        "multi-site", "multi site", "property", "landlord", "tenant",
        "network operator", "roaming", "emsp", "cpo",
    ],
}

_DEFECT_BOOST = 0.05  # defects get a small confidence boost per matched term


@dataclass
class RoutingResult:
    pod: Pod
    confidence: float
    matched_keywords: list[str]


class PodRoutingService:
    def route(self, title: str, description: str, request_type: RequestType) -> RoutingResult:
        """Score each pod against the request text and return the best match."""
        text = f"{title} {description}".lower()
        scores: dict[Pod, list[str]] = {pod: [] for pod in _KEYWORDS}

        for pod, keywords in _KEYWORDS.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", text):
                    scores[pod].append(kw)

        best_pod = Pod.UNKNOWN
        best_count = 0
        for pod, matched in scores.items():
            if len(matched) > best_count:
                best_count = len(matched)
                best_pod = pod

        if best_pod == Pod.UNKNOWN or best_count == 0:
            return RoutingResult(pod=Pod.UNKNOWN, confidence=0.0, matched_keywords=[])

        # Confidence: base 0.60 + 0.05 per keyword hit, capped at 0.95
        boost = _DEFECT_BOOST if request_type == RequestType.DEFECT else 0.0
        confidence = min(0.60 + (best_count * 0.05) + boost, 0.95)
        return RoutingResult(
            pod=best_pod,
            confidence=round(confidence, 2),
            matched_keywords=scores[best_pod],
        )

    def get_jira_project(self, pod: Pod) -> str:
        return settings.jira_project_map.get(pod, settings.JIRA_PROJECT_DATA)

    def get_teams_webhook(self, pod: Pod) -> str:
        return settings.TEAMS_WEBHOOK_URL

    def get_pm_email(self, pod: Pod) -> str | None:
        return None

    def get_assignee_email(self, pod: Pod) -> str | None:
        _POD_ASSIGNEE: dict[Pod, str] = {
            Pod.CHARGER: "jraza@blinkcharging.com",
        }
        return _POD_ASSIGNEE.get(pod)
