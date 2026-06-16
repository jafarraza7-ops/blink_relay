"""
Locust load test suite for Blink Relay
Tests critical paths: request creation, listing, messaging, status updates, analytics
"""
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import random
import json
import time
from typing import Optional


class BRUser(FastHttpUser):
    """Base Blink Relay user simulating real usage patterns"""

    wait_time = between(1, 3)

    def on_start(self):
        """Authenticate before starting tasks"""
        self.access_token = None
        self.user_email = f"load_test_{random.randint(1000, 9999)}@test.com"
        self.user_id = None
        self.request_ids = []
        self.authenticate()

    def authenticate(self):
        """Get login token"""
        try:
            self.access_token = self._generate_test_token()
            self.user_id = f"user-{random.randint(1000, 9999)}"
        except Exception as e:
            self.on_fail(f"Authentication failed: {e}")

    def _generate_test_token(self) -> str:
        """Generate a test JWT token"""
        import uuid
        return f"test_token_{uuid.uuid4().hex[:16]}"

    def _get_headers(self) -> dict:
        """Get authorization headers"""
        if not self.access_token:
            self.authenticate()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def on_fail(self, msg: str):
        """Handle test failures gracefully"""
        print(f"[{self.user_email}] {msg}")

    # Task weights (higher = runs more frequently)
    @task(10)
    def list_requests_default(self):
        """GET /requests - List all requests"""
        self.client.get("/api/requests", headers=self._get_headers(), name="/requests?GET")

    @task(8)
    def list_requests_with_filter(self):
        """GET /requests with filters"""
        filters = {
            "status": random.choice(["Submitted", "InReview", "Approved"]),
            "priority": random.choice(["High", "Medium"]),
            "skip": 0,
            "limit": 20
        }
        query = "&".join([f"{k}={v}" for k, v in filters.items()])
        self.client.get(f"/api/requests?{query}", headers=self._get_headers(), name="/requests?filtered")

    @task(5)
    def get_user_requests(self):
        """GET /requests/mine - Submitter's own requests"""
        self.client.get("/api/requests/mine", headers=self._get_headers(), name="/requests/mine")

    @task(6)
    def create_request(self):
        """POST /requests - Submit new request"""
        payload = {
            "request_type": random.choice(["Feature", "Defect"]),
            "title": f"Load Test Request {random.randint(1, 1000)}",
            "priority": random.choice(["High", "Medium", "Low"]),
            "pod": random.choice(["Driver", "Charge", "Host", "Ops"]),
            "region": ["NA"],
            "business_problem": "Testing load handling",
            "expected_outcome": "System remains responsive",
            "affected_area": "Integration"
        }
        resp = self.client.post("/api/requests", json=payload, headers=self._get_headers(), name="/requests?POST")
        if resp.status_code == 201:
            try:
                data = resp.json()
                self.request_ids.append(data.get("id"))
            except:
                pass

    @task(4)
    def get_request_detail(self):
        """GET /requests/{id} - View single request"""
        if not self.request_ids:
            return
        req_id = random.choice(self.request_ids)
        self.client.get(f"/api/requests/{req_id}", headers=self._get_headers(), name="/requests/{id}")

    @task(3)
    def update_request_status(self):
        """PATCH /requests/{id} - Update request"""
        if not self.request_ids:
            return
        req_id = random.choice(self.request_ids)
        payload = {"status": random.choice(["InReview", "AwaitingInfo"]), "priority": random.choice(["High", "Medium"])}
        self.client.patch(f"/api/requests/{req_id}", json=payload, headers=self._get_headers(), name="/requests/{id}?PATCH")

    @task(5)
    def add_message(self):
        """POST /requests/{id}/messages - Add comment"""
        if not self.request_ids:
            return
        req_id = random.choice(self.request_ids)
        payload = {"body": f"Load test message {random.randint(1, 100)}", "is_internal": random.choice([True, False])}
        self.client.post(f"/api/requests/{req_id}/messages", json=payload, headers=self._get_headers(), name="/requests/{id}/messages?POST")

    @task(4)
    def get_messages(self):
        """GET /requests/{id}/messages - Fetch conversation"""
        if not self.request_ids:
            return
        req_id = random.choice(self.request_ids)
        self.client.get(f"/api/requests/{req_id}/messages", headers=self._get_headers(), name="/requests/{id}/messages?GET")

    @task(5)
    def get_analytics_summary(self):
        """GET /analytics/summary - Dashboard overview"""
        self.client.get("/api/analytics/summary", headers=self._get_headers(), name="/analytics/summary")

    @task(3)
    def get_request_aging(self):
        """GET /analytics/request-aging - Aging metrics"""
        self.client.get("/api/analytics/request-aging", headers=self._get_headers(), name="/analytics/request-aging")

    @task(2)
    def get_pod_performance(self):
        """GET /analytics/pod-performance - Pod metrics"""
        self.client.get("/api/analytics/pod-performance", headers=self._get_headers(), name="/analytics/pod-performance")

    @task(2)
    def export_requests(self):
        """GET /requests/export - CSV export"""
        self.client.get("/api/requests/export", headers=self._get_headers(), name="/requests/export")

    @task(1)
    def get_request_timeline(self):
        """GET /requests/{id}/timeline - View history"""
        if not self.request_ids:
            return
        req_id = random.choice(self.request_ids)
        self.client.get(f"/api/requests/{req_id}/timeline", headers=self._get_headers(), name="/requests/{id}/timeline")


class LightLoadUser(BRUser):
    """Light user - minimal activity"""
    wait_time = between(3, 8)
    create_request = lambda self: None
    update_request_status = lambda self: None
    cancel_request = lambda self: None


class HeavyLoadUser(BRUser):
    """Heavy user - maximum activity (PM)"""
    wait_time = between(0.5, 2)
