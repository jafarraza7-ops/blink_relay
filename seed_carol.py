#!/usr/bin/env python3
"""Create 25 requests from carol.requestor@ethereal.email with varied type/region/pod."""
import requests as http
import sys
import json

BASE = "http://localhost:8001"
EMAIL = "carol.requestor@ethereal.email"

def get_jwt():
    r = http.post(f"{BASE}/api/auth/email/dev/get-token", json={"email": EMAIL})
    r.raise_for_status()
    token = r.json()["token"]
    r2 = http.post(f"{BASE}/api/auth/email/verify-token", json={"token": token})
    r2.raise_for_status()
    return r2.json()["access_token"]

def get_csrf(jwt):
    r = http.get(f"{BASE}/health", headers={"Authorization": f"Bearer {jwt}"})
    return r.headers.get("X-CSRF-Token", "")

# 25 requests: cycling through all combinations
# pods: Charger, Driver, Revenue, Data, DevOps, Denali (6)
# types: Feature, Defect (2)
# regions: NA, UK, EU (3)
REQUESTS = [
    # pod, type, region, title
    ("Charger", "Feature", "NA", "Add dynamic load balancing for Level 2 chargers"),
    ("Driver", "Defect", "UK", "Driver app crashes on iOS 17 when starting session"),
    ("Revenue", "Feature", "EU", "Add invoice download in EUR currency"),
    ("Data", "Defect", "NA", "Dashboard analytics missing last 24h data points"),
    ("DevOps", "Feature", "UK", "Implement blue-green deployment pipeline"),
    ("Denali", "Defect", "EU", "Denali firmware update fails on v2.3 hardware"),
    ("Charger", "Defect", "UK", "Charger goes offline after extended idle period"),
    ("Driver", "Feature", "NA", "Add ride-share integration for EV fleets"),
    ("Revenue", "Defect", "EU", "Payment processing timeout on weekend peak hours"),
    ("Data", "Feature", "UK", "Export usage reports to CSV from admin portal"),
    ("DevOps", "Defect", "NA", "CI pipeline fails intermittently on Docker build step"),
    ("Denali", "Feature", "UK", "Add over-the-air firmware update scheduling"),
    ("Charger", "Feature", "EU", "Support OCPP 2.0.1 smart charging profiles"),
    ("Driver", "Defect", "NA", "EV routing shows incorrect charging station status"),
    ("Revenue", "Feature", "UK", "Introduce subscription pricing tier for fleet customers"),
    ("Data", "Defect", "EU", "Telemetry data pipeline drops records under high load"),
    ("DevOps", "Feature", "NA", "Add Terraform modules for multi-region deployment"),
    ("Denali", "Defect", "UK", "Denali unit loses MQTT connection after 6 hours"),
    ("Charger", "Feature", "NA", "Implement remote reboot capability via admin portal"),
    ("Driver", "Feature", "EU", "Localize driver app to German and French"),
    ("Revenue", "Defect", "NA", "Discount codes not applying correctly at checkout"),
    ("Data", "Feature", "EU", "Real-time energy consumption heatmap dashboard"),
    ("DevOps", "Defect", "UK", "Log aggregation missing container restart events"),
    ("Denali", "Feature", "NA", "Add cellular fallback when Wi-Fi is unavailable"),
    ("Charger", "Defect", "EU", "DC fast charger power output drops to 50% after 20 min"),
]

PRIORITY_CYCLE = ["Low", "Medium", "High", "Critical"]

def main():
    print("Getting Carol's JWT...")
    jwt = get_jwt()
    csrf = get_csrf(jwt)
    headers = {
        "Authorization": f"Bearer {jwt}",
        "X-CSRF-Token": csrf,
        "Content-Type": "application/json",
    }

    created = 0
    failed = 0

    for i, (pod, req_type, region, title) in enumerate(REQUESTS):
        priority = PRIORITY_CYCLE[i % len(PRIORITY_CYCLE)]
        payload = {
            "title": title,
            "request_type": req_type,
            "pod": pod,
            "region": [region],
            "priority": priority,
            "business_problem": f"[Requestor-seeded] {title}. This request covers the {pod} pod for the {region} region.",
            "expected_outcome": f"Expected: {title} is implemented or resolved with minimal impact to existing workflows.",
            "affected_area": pod,
        }
        r = http.post(f"{BASE}/api/requests", json=payload, headers=headers)
        if r.status_code in (200, 201):
            data = r.json()
            rid = data.get("id", "?")
            jsm = data.get("jsm_ticket_key", "pending")
            print(f"  [{i+1:02d}] OK  {pod:10s} | {req_type:7s} | {region:3s} | id={rid} jsm={jsm}")
            created += 1
        else:
            print(f"  [{i+1:02d}] ERR {pod:10s} | {req_type:7s} | {region:3s} | {r.status_code} {r.text[:100]}")
            failed += 1

    print(f"\nDone: {created} created, {failed} failed")

if __name__ == "__main__":
    main()
