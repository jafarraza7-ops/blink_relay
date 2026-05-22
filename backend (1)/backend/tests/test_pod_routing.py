from __future__ import annotations

import pytest

from app.models.request import Pod, RequestType
from app.services.pod_routing_service import PodRoutingService


@pytest.fixture
def svc():
    return PodRoutingService()


def test_route_charger_keywords(svc: PodRoutingService):
    result = svc.route("OCPP firmware crash on level 2 charger", "The charger firmware is causing repeated crashes on the EVSE unit", RequestType.DEFECT)
    assert result.pod == Pod.CHARGER
    assert result.confidence >= 0.65


def test_route_driver_keywords(svc: PodRoutingService):
    result = svc.route("Driver mobile app checkout flow broken", "The iOS app crashes during checkout session start", RequestType.DEFECT)
    assert result.pod == Pod.DRIVER
    assert result.confidence >= 0.65


def test_route_revenue_keywords(svc: PodRoutingService):
    result = svc.route("Billing invoice generation failure", "Payment processing via Stripe is failing for subscription renewals", RequestType.DEFECT)
    assert result.pod == Pod.REVENUE
    assert result.confidence >= 0.65


def test_route_data_keywords(svc: PodRoutingService):
    result = svc.route("Analytics dashboard performance", "The report pipeline and data warehouse queries are timing out", RequestType.FEATURE)
    assert result.pod == Pod.DATA
    assert result.confidence >= 0.65


def test_route_devops_keywords(svc: PodRoutingService):
    result = svc.route("Kubernetes deployment pipeline failing", "CI/CD pipeline for docker deploy is broken, infrastructure alert is firing", RequestType.DEFECT)
    assert result.pod == Pod.DEVOPS
    assert result.confidence >= 0.65


def test_route_denali_keywords(svc: PodRoutingService):
    result = svc.route("Enterprise fleet multi-site management", "B2B commercial network operator needs multi-site depot support", RequestType.FEATURE)
    assert result.pod == Pod.DENALI
    assert result.confidence >= 0.65


def test_route_unknown_returns_low_confidence(svc: PodRoutingService):
    result = svc.route("Miscellaneous generic request", "No specific keywords here at all", RequestType.FEATURE)
    assert result.pod == Pod.UNKNOWN
    assert result.confidence == 0.0


def test_defect_gets_confidence_boost(svc: PodRoutingService):
    feature_result = svc.route("Driver app profile", "Update the user profile account mobile page", RequestType.FEATURE)
    defect_result = svc.route("Driver app profile", "Update the user profile account mobile page", RequestType.DEFECT)
    if feature_result.pod == defect_result.pod == Pod.DRIVER:
        assert defect_result.confidence >= feature_result.confidence


def test_get_jira_project(svc: PodRoutingService):
    from app.core.config import get_settings
    settings = get_settings()
    assert svc.get_jira_project(Pod.CHARGER) == settings.JIRA_PROJECT_CHARGER
    assert svc.get_jira_project(Pod.DRIVER) == settings.JIRA_PROJECT_DRIVER
    assert svc.get_jira_project(Pod.REVENUE) == settings.JIRA_PROJECT_REVENUE


def test_confidence_cap(svc: PodRoutingService):
    title = "driver mobile ios android app checkout session start stop notification rfid card"
    body = "driver mobile ios android app checkout session start stop notification rfid card user experience"
    result = svc.route(title, body, RequestType.FEATURE)
    assert result.confidence <= 0.95


def test_matched_keywords_populated(svc: PodRoutingService):
    result = svc.route("Charger firmware crash", "EVSE hardware malfunction", RequestType.DEFECT)
    if result.pod == Pod.CHARGER:
        assert len(result.matched_keywords) > 0
