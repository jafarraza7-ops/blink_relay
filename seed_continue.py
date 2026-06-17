"""
seed_continue.py — Two jobs:
  1. Backfill JSM mock tickets on the 103 existing requests (no jsm_ticket_key).
  2. Create the remaining 107 requests (indices 103-209) to reach 210 total.
"""
import sys, time, random
import requests as http
import asyncio, asyncpg

BASE  = "http://localhost:8001"
EMAIL = "alf.adams49@ethereal.email"
DB_DSN = "postgresql://jraza@localhost/blink_relay"

PODS      = ["Charger", "Driver", "Revenue", "Data", "DevOps", "Denali"]
TYPES     = ["Feature", "Defect"]
REGIONS   = ["NA", "UK", "EU"]
PRIORITIES = ["Critical", "High", "Medium", "Low"]

TEMPLATES = {
    "Charger": {
        "Feature": [
            ("Smart Load Balancing for Multi-Unit Sites",
             "Large commercial sites with 20+ chargers are tripping circuit breakers during peak hours.",
             "Implement dynamic load balancing that redistributes power across chargers in real time.",
             "EV charging infrastructure at commercial properties"),
            ("Remote Charger Firmware OTA Update",
             "Field technicians spend 2-3 hours on-site for each firmware update across thousands of units.",
             "Enable over-the-air firmware updates triggered from the management portal.",
             "Charger firmware management"),
            ("Scheduled Charging Windows for Off-Peak Hours",
             "Fleet operators want to schedule charging overnight when electricity rates are lower.",
             "Allow operators to define charging windows per charger or group.",
             "Fleet charging management"),
            ("Charger Health Dashboard with Predictive Alerts",
             "Unexpected charger outages result in lost revenue and poor driver experience.",
             "ML-based dashboard showing charger health scores with alerts 48h before failure.",
             "Charger monitoring and maintenance"),
            ("Multi-Network Interoperability (OCPI 2.2.1)",
             "Blink chargers cannot be discovered by third-party apps like PlugShare.",
             "Implement OCPI 2.2.1 protocol for cross-network roaming.",
             "Network interoperability and EV roaming"),
        ],
        "Defect": [
            ("Charger Session Not Ending After Cable Unplug",
             "Drivers unplug cable but session stays active, causing double billing.",
             "Add cable disconnect detection to auto-terminate sessions.",
             "Charger session lifecycle"),
            ("RFID Card Auth Intermittently Failing on Level 2 Units",
             "~3% of RFID swipes fail silently on Level 2 chargers in cold weather.",
             "Debug authentication timeout issue in sub-zero temperatures.",
             "RFID authentication"),
            ("Charger Offline Status Not Updating in Portal",
             "Portal shows charger as Online up to 45 minutes after it goes offline.",
             "Fix heartbeat polling interval and status cache invalidation.",
             "Charger status monitoring"),
            ("Connector Lock Mechanism Failure on DC Fast Chargers",
             "CCS connector lock fails to disengage on ~1% of sessions, requiring manual override.",
             "Fix timing issue in lock/unlock sequence during session teardown.",
             "Hardware-software interface for DC fast chargers"),
            ("Incorrect kWh Reporting on Level 3 Units",
             "Energy meter readings show 8-12% variance vs utility meter, causing billing disputes.",
             "Calibrate kWh meter integration and add validation checks.",
             "Energy metering and billing accuracy"),
        ],
    },
    "Driver": {
        "Feature": [
            ("Trip-Aware Charging Stop Recommendations",
             "Drivers on long trips don't know which charging stops to plan for.",
             "Integrate route planning with charging stop suggestions based on vehicle range.",
             "Driver mobile app navigation"),
            ("Saved Payment Methods with Apple Pay / Google Pay",
             "Re-entering card details for each session increases checkout friction.",
             "Add wallet support for one-tap payments on the driver app.",
             "Driver payment experience"),
            ("Real-Time Queue Visibility at Busy Stations",
             "Drivers arrive at stations to find all ports occupied with no wait time info.",
             "Show live queue length and estimated wait time per station.",
             "Driver station discovery"),
            ("Carbon Offset Tracking per Charging Session",
             "ESG-conscious drivers want to track their emissions savings.",
             "Add CO2 savings dashboard showing lifetime impact vs gasoline equivalent.",
             "Driver engagement and sustainability"),
            ("Group Charging for Rideshare Fleets",
             "Rideshare drivers at the same depot can't split a single bill.",
             "Enable fleet group billing where drivers charge individually but bill to one account.",
             "Driver fleet management"),
        ],
        "Defect": [
            ("App Crashes on Session Start for Android 14 Users",
             "All Android 14 users (22% of base) experience crash on 'Start Charging' tap.",
             "Fix NFC permission handling regression introduced in Android 14.",
             "Driver mobile app Android"),
            ("Push Notifications Not Delivered When App in Background",
             "Session complete notifications arrive 15-45 min late or not at all on iOS.",
             "Debug APNs token refresh issue affecting background notification delivery.",
             "Driver notification system"),
            ("Map Shows Chargers 0.3 Miles Off Actual Location",
             "GPS coordinates in the database are off by ~500m for 180 stations in Texas.",
             "Audit and correct station coordinates for affected sites.",
             "Driver station map accuracy"),
            ("Session History Showing Duplicate Charges",
             "1.2% of users see the same session listed twice in billing history.",
             "Fix race condition in session write-back from charger to driver profile.",
             "Driver billing history"),
            ("Account Login Broken After Password Reset on iOS 17",
             "Users who reset password on web cannot log into iOS app with new credentials.",
             "Fix token invalidation not propagating to mobile auth cache.",
             "Driver authentication"),
        ],
    },
    "Revenue": {
        "Feature": [
            ("Dynamic Pricing Based on Grid Demand",
             "Flat-rate pricing doesn't maximize revenue during peak demand windows.",
             "Implement time-of-use pricing engine with real-time grid signal integration.",
             "Revenue pricing engine"),
            ("Subscription Plan for Frequent Charging Members",
             "High-frequency drivers (>8 sessions/month) have no loyalty incentive.",
             "Launch monthly subscription with unlimited charging at discounted kWh rate.",
             "Driver monetization"),
            ("Automated Refund Processing for Failed Sessions",
             "Finance team manually processes 200+ refunds per week for failed sessions.",
             "Auto-detect failed sessions and trigger refund within 24h without manual review.",
             "Billing and refund automation"),
            ("Multi-Currency Support for EU Market Expansion",
             "EU site operators cannot price in EUR; all billing defaults to USD.",
             "Add currency localization to billing engine with exchange rate sync.",
             "International billing"),
            ("Invoice Generation for B2B Fleet Accounts",
             "Enterprise fleet customers require monthly invoices with cost center codes.",
             "Build automated invoice engine with custom line items and PO number support.",
             "B2B billing and invoicing"),
        ],
        "Defect": [
            ("Stripe Webhook Failures Causing Missing Payment Records",
             "0.4% of Stripe payment.succeeded webhooks are dropped, leaving unpaid sessions.",
             "Add idempotency key validation and retry queue for webhook processing.",
             "Payment webhook reliability"),
            ("Incorrect VAT Calculation on UK Invoices",
             "UK invoices are showing 0% VAT instead of 20% for post-Brexit transactions.",
             "Fix tax jurisdiction logic for UK billing addresses.",
             "Tax calculation for UK market"),
            ("Promo Code Applying Discount Multiple Times",
             "Single-use promo codes can be redeemed up to 5 times before being invalidated.",
             "Add atomic check-and-mark on promo code redemption.",
             "Promo code system"),
            ("Revenue Reports Double-Counting Split Sessions",
             "Sessions spanning midnight appear twice in daily revenue reports.",
             "Fix session revenue attribution to use session start date only.",
             "Revenue reporting"),
            ("Credit Card Expiry Date Validation Accepting Past Dates",
             "Payment form accepts expired card dates without showing an error.",
             "Add client and server-side validation for card expiry dates.",
             "Payment form validation"),
        ],
    },
    "Data": {
        "Feature": [
            ("Real-Time Charger Utilization Dashboard",
             "Operations team lacks live visibility into network-wide charger utilization.",
             "Build Grafana-style dashboard with 1-min refresh showing utilization heatmap.",
             "Operations analytics"),
            ("ML Demand Forecasting for Station Capacity Planning",
             "New station placements are based on gut feel rather than demand signals.",
             "Build 90-day demand forecast model using session history, demographics, EV adoption curves.",
             "Station expansion strategy"),
            ("Automated Anomaly Detection for Billing Outliers",
             "Billing anomalies (10x normal charges) are caught manually 3-5 days after occurrence.",
             "Deploy unsupervised anomaly detection on billing events with real-time alerting.",
             "Billing data quality"),
            ("Data Lake Migration from On-Prem to Azure Synapse",
             "Current Redshift cluster is at 94% storage capacity with no headroom.",
             "Migrate all historical session data to Azure Synapse with zero-downtime cutover.",
             "Data infrastructure"),
            ("Self-Serve Analytics Portal for Site Operators",
             "Site operators submit 50+ ad-hoc data requests to the data team per month.",
             "Launch no-code analytics portal with pre-built templates for site performance.",
             "Operator self-service reporting"),
        ],
        "Defect": [
            ("Dbt Pipeline Failing on Incremental Loads > 500k Rows",
             "Nightly dbt run times out after 6 hours when incremental batch exceeds 500k rows.",
             "Optimize incremental model strategy and add partition pruning.",
             "Data pipeline reliability"),
            ("Session Duration Showing Negative Values in Reports",
             "2,300 session records have negative durations due to timezone offset bug.",
             "Fix UTC conversion in session duration calculation and backfill affected records.",
             "Session data quality"),
            ("Looker Dashboard Not Reflecting Latest Charger Additions",
             "New chargers added in the last 30 days don't appear in Looker dashboards.",
             "Fix charger dimension refresh job that's skipping records with null installation dates.",
             "Business intelligence"),
            ("Data Warehouse Missing 6 Days of Events (March 2026)",
             "Kafka consumer lag caused event loss between March 12-18. Gap exists in warehouse.",
             "Replay missing events from Kafka retention and patch affected aggregates.",
             "Event streaming and data recovery"),
            ("PII Data Appearing in Non-Masked Analytics Tables",
             "Raw email addresses visible in analytics_sessions table accessed by BI contractors.",
             "Apply tokenization to all PII fields in the analytics layer.",
             "Data governance and privacy"),
        ],
    },
    "DevOps": {
        "Feature": [
            ("Blue-Green Deployment Pipeline for Zero-Downtime Releases",
             "Current deployments cause 2-4 minute downtime affecting 40k active sessions.",
             "Implement blue-green deployment with automatic traffic cutover and rollback.",
             "CI/CD and deployment"),
            ("Automated Security Scanning in CI Pipeline",
             "Security vulnerabilities are discovered in production rather than at commit time.",
             "Integrate Snyk + SAST tools into GitHub Actions with blocking PR checks.",
             "Application security"),
            ("Kubernetes Auto-Scaling for Charger Event Ingestion",
             "Ingestion pods crash during peak hours (5-7pm) when event volume spikes 8x.",
             "Configure HPA with custom metrics based on Kafka consumer lag.",
             "Infrastructure scaling"),
            ("Secrets Management Migration to Azure Key Vault",
             "Credentials are stored in environment variables and GitHub Secrets inconsistently.",
             "Centralize all secrets in Azure Key Vault with automated rotation.",
             "Security and secrets management"),
            ("Observability Stack: Distributed Tracing with OpenTelemetry",
             "Debugging cross-service latency issues requires manual log correlation.",
             "Deploy OpenTelemetry collector with Jaeger backend for end-to-end trace visualization.",
             "Platform observability"),
        ],
        "Defect": [
            ("Terraform State Locking Causing Blocked Deployments",
             "Azure Blob backend state lock not releasing after failed plan, blocking all deploys.",
             "Add state lock TTL and implement force-unlock automation for stuck locks.",
             "Infrastructure as code"),
            ("Container Image Builds Failing Due to npm Audit Errors",
             "CI pipeline exits on npm audit with 2 critical vulnerabilities (non-blocking in dev).",
             "Add --audit-level=high flag to only block on critical vulnerabilities.",
             "Build pipeline"),
            ("Log Aggregation Missing Events from 3 AKS Nodes",
             "Fluent Bit DaemonSet not running on 3 spot nodes after last node pool recycle.",
             "Fix DaemonSet toleration to schedule on all node types including spot.",
             "Log aggregation"),
            ("SSL Certificate Not Auto-Renewing on staging.blinkcharging.com",
             "Cert-manager ACME challenge failing due to ingress annotation mismatch.",
             "Fix cert-manager ClusterIssuer configuration for wildcard cert renewal.",
             "TLS certificate management"),
            ("Redis Sentinel Failover Taking 90s Instead of <10s",
             "During Redis primary failure, app experiences 90s of 500 errors.",
             "Tune Sentinel quorum settings and min-slaves-to-write parameter.",
             "Cache reliability"),
        ],
    },
    "Denali": {
        "Feature": [
            ("Fleet Management Portal for Enterprise Customers",
             "Enterprise fleet operators manage 500+ vehicles with no dedicated portal.",
             "Build white-labeled fleet portal with vehicle assignment, billing, and reporting.",
             "Enterprise fleet management"),
            ("API Access for Fleet Telematics Integration",
             "Fleet operators using Samsara/Geotab cannot correlate charging events with vehicle data.",
             "Publish authenticated REST + webhook API for telematics platform integration.",
             "Enterprise API platform"),
            ("Role-Based Access Control for Multi-Site Enterprises",
             "A single admin account is shared across 15 staff at large enterprise accounts.",
             "Implement RBAC with site-level, region-level, and global permission scopes.",
             "Enterprise access management"),
            ("Custom Branding for White-Label Enterprise Deployments",
             "Enterprise customers (airports, malls) require their own brand on the charging experience.",
             "Build theming engine supporting custom logos, colors, and domain per enterprise account.",
             "Enterprise customization"),
            ("Dedicated Account Manager Dashboard",
             "Account managers track SLA and escalations across enterprise accounts in spreadsheets.",
             "Build internal dashboard showing SLA compliance, open issues, and usage trends per account.",
             "Enterprise account management"),
        ],
        "Defect": [
            ("Enterprise SSO (SAML 2.0) Login Failing for Okta Tenants",
             "Okta-integrated enterprise customers cannot SSO after the March Azure AD migration.",
             "Fix SAML assertion signature validation for non-Azure IdPs.",
             "Enterprise authentication"),
            ("Fleet Billing Export Missing Vehicles Added After Jan 2026",
             "Monthly CSV export for fleet billing omits vehicles enrolled after January 1, 2026.",
             "Fix fleet enrollment date filter in billing export job.",
             "Fleet billing accuracy"),
            ("Depot Charging Report Showing Wrong Time Zone for UK Sites",
             "UK depot reports show session times in UTC instead of BST.",
             "Apply site timezone offset to all report timestamps for UK locations.",
             "Enterprise reporting"),
            ("Enterprise API Rate Limits Not Enforced Per Customer",
             "One enterprise customer hitting 10k req/min is degrading performance for others.",
             "Implement per-API-key rate limiting at the gateway layer.",
             "Enterprise API reliability"),
            ("Vehicle-to-Charger Pairing Lost After Fleet Portal Logout",
             "Drivers lose their assigned charger pairing when fleet admin logs out.",
             "Fix session scoping so vehicle-charger assignments persist across admin sessions.",
             "Fleet session management"),
        ],
    },
}

def build_payload(idx):
    pod      = PODS[idx % len(PODS)]
    rtype    = TYPES[idx % len(TYPES)]
    region   = REGIONS[idx % len(REGIONS)]
    priority = PRIORITIES[idx % len(PRIORITIES)]
    tmpl_list = TEMPLATES[pod][rtype]
    tmpl = tmpl_list[idx % len(tmpl_list)]
    title, biz, outcome, area = tmpl
    suffix = f" (#{idx + 1})"
    payload = {
        "title": title + suffix,
        "request_type": rtype,
        "pod": pod,
        "region": [region],
        "priority": priority,
        "business_problem": biz,
        "expected_outcome": outcome,
        "affected_area": area,
    }
    if rtype == "Defect":
        payload["steps_to_reproduce"] = (
            f"1. Reproduce in {region} environment\n"
            f"2. Observe the issue described above\n"
            f"3. Compare with expected behavior"
        )
    return payload


def get_jwt():
    r = http.post(f"{BASE}/api/auth/email/dev/get-token", json={"email": EMAIL})
    r.raise_for_status()
    r2 = http.post(f"{BASE}/api/auth/email/verify-token", json={"token": r.json()["token"]})
    r2.raise_for_status()
    return r2.json()["access_token"]


def get_csrf(jwt):
    """Fetch CSRF token from any GET endpoint's response headers."""
    r = http.get(f"{BASE}/health", headers={"Authorization": f"Bearer {jwt}"})
    csrf = r.headers.get("X-CSRF-Token", "")
    if not csrf:
        # Fallback: hit an authenticated endpoint
        r2 = http.get(f"{BASE}/api/requests/mine", headers={"Authorization": f"Bearer {jwt}"})
        csrf = r2.headers.get("X-CSRF-Token", "")
    return csrf


def main():
    print("Getting JWT + CSRF token...")
    jwt = get_jwt()
    csrf = get_csrf(jwt)
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
    }
    print(f"  CSRF: {csrf[:30]}...")

    # ── Part 1: backfill JSM on existing requests directly via DB ─────────────
    print("\n[1/2] Backfilling JSM mock tickets on existing requests via DB...")
    import subprocess, random as _r

    # Generate and run one UPDATE per request missing a JSM ticket
    sql = """
DO $$
DECLARE
  r RECORD;
  fake_key TEXT;
BEGIN
  FOR r IN SELECT id FROM requests WHERE jsm_ticket_key IS NULL LOOP
    fake_key := 'BLR-' || (1000 + floor(random() * 8999))::int;
    UPDATE requests
      SET jsm_ticket_key = fake_key,
          jsm_ticket_url = 'https://blinkcharging.atlassian.net/servicedesk/customer/portal/1/' || fake_key
    WHERE id = r.id;
  END LOOP;
END $$;
"""
    result = subprocess.run(
        ["/Users/jraza/Applications/Postgres.app/Contents/Versions/16/bin/psql",
         "-U", "jraza", "-d", "blink_relay", "-c", sql],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        count_r = subprocess.run(
            ["/Users/jraza/Applications/Postgres.app/Contents/Versions/16/bin/psql",
             "-U", "jraza", "-d", "blink_relay", "-t", "-c",
             "SELECT COUNT(*) FROM requests WHERE jsm_ticket_key IS NOT NULL"],
            capture_output=True, text=True
        )
        print(f"      ✓ JSM tickets present on {count_r.stdout.strip()} requests")
    else:
        print(f"      ✗ Backfill error: {result.stderr[:300]}")

    # ── Part 2: create remaining requests (103 → 209) ─────────────────────────
    START = 167
    END   = 210
    total = END - START
    print(f"\n[2/2] Creating {total} more requests (#{START+1}–#{END})...")

    ok, failed = 0, 0
    for i in range(START, END):
        payload = build_payload(i)
        try:
            resp = http.post(f"{BASE}/api/requests", json=payload, headers=headers, timeout=15)
            if resp.status_code == 201:
                data = resp.json()
                ok += 1
                print(f"  [{ok:>3}/{total}] ✓ {data['reference_id']}  [{payload['pod']:8}] [{payload['request_type']:7}] [{payload['region'][0]}]  {payload['title'][:55]}")
            else:
                failed += 1
                print(f"  [{i-START+1:>3}/{total}] ✗ HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            failed += 1
            print(f"  [{i-START+1:>3}/{total}] ✗ {e}")
        time.sleep(0.15)

    print(f"\nDone.  New requests created: {ok}  Failed: {failed}")

    import subprocess
    count_r = subprocess.run(
        ["/Users/jraza/Applications/Postgres.app/Contents/Versions/16/bin/psql",
         "-U", "jraza", "-d", "blink_relay", "-t", "-c", "SELECT COUNT(*) FROM requests"],
        capture_output=True, text=True
    )
    print(f"Total requests in DB: {count_r.stdout.strip()}")


if __name__ == "__main__":
    main()
