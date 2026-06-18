"""
scripts/send_coverage_report.py

Parse a pytest coverage XML report and send a formatted HTML summary
email to the PM group via SMTP.

Usage (called from GitHub Actions after pytest --cov-report=xml):
    python scripts/send_coverage_report.py --xml coverage.xml \
        --smtp-host smtp.ethereal.email \
        --smtp-port 587 \
        --smtp-user <user> \
        --smtp-pass <pass> \
        --smtp-from "Blink Relay CI <noreply@blinkcharging.com>" \
        --to pms@blinkcharging.com \
        --run-url https://github.com/...  \
        --branch main
"""
from __future__ import annotations

import argparse
import smtplib
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def parse_coverage(xml_path: str) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    total_line_rate = float(root.attrib.get("line-rate", 0))
    total_branch_rate = float(root.attrib.get("branch-rate", 0))
    total_lines = int(root.attrib.get("lines-valid", 0))
    covered_lines = int(root.attrib.get("lines-covered", 0))
    missed_lines = total_lines - covered_lines

    packages = []
    for pkg in root.iter("package"):
        pkg_name = pkg.attrib.get("name", "")
        pkg_rate = float(pkg.attrib.get("line-rate", 0))
        packages.append({
            "name": pkg_name,
            "pct": round(pkg_rate * 100, 1),
        })

    packages.sort(key=lambda p: p["pct"])

    return {
        "total_pct": round(total_line_rate * 100, 1),
        "branch_pct": round(total_branch_rate * 100, 1),
        "total_lines": total_lines,
        "covered_lines": covered_lines,
        "missed_lines": missed_lines,
        "packages": packages,
    }


def coverage_color(pct: float) -> str:
    if pct >= 80:
        return "#16a34a"  # green
    if pct >= 60:
        return "#d97706"  # amber
    return "#dc2626"      # red


def build_html(data: dict, branch: str, run_url: str, date_str: str) -> str:
    total_pct = data["total_pct"]
    color = coverage_color(total_pct)

    pkg_rows = ""
    for pkg in data["packages"]:
        c = coverage_color(pkg["pct"])
        pkg_rows += f"""
        <tr>
          <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#374151;">{pkg["name"]}</td>
          <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;color:{c};font-weight:600;text-align:right;">{pkg["pct"]}%</td>
        </tr>"""

    ci_link = f'<a href="{run_url}" style="color:#1d4ed8;">View CI Run →</a>' if run_url else ""

    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">

      <!-- Header -->
      <tr>
        <td style="background:#1e3a5f;padding:24px 32px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <div style="display:inline-flex;align-items:center;gap:8px;">
                  <div style="background:#3b82f6;border-radius:6px;width:28px;height:28px;display:inline-block;text-align:center;line-height:28px;">
                    <span style="color:#fff;font-size:16px;">⚡</span>
                  </div>
                  <span style="color:#ffffff;font-size:18px;font-weight:700;">Blink Relay</span>
                </div>
                <p style="color:#93c5fd;font-size:13px;margin:4px 0 0;">Weekly Test Coverage Report</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- Coverage badge -->
      <tr>
        <td style="padding:32px 32px 0;">
          <h1 style="font-size:22px;color:#111827;margin:0 0 4px;">Coverage Report</h1>
          <p style="color:#6b7280;font-size:14px;margin:0 0 24px;">Week of {date_str} · Branch: <strong>{branch}</strong></p>

          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td width="33%" style="text-align:center;padding:16px;background:#f3f4f6;border-radius:8px;margin-right:8px;">
                <div style="font-size:36px;font-weight:700;color:{color};">{total_pct}%</div>
                <div style="font-size:12px;color:#6b7280;margin-top:4px;">Line Coverage</div>
              </td>
              <td width="4%"></td>
              <td width="33%" style="text-align:center;padding:16px;background:#f3f4f6;border-radius:8px;">
                <div style="font-size:36px;font-weight:700;color:#1e3a5f;">{data["covered_lines"]}</div>
                <div style="font-size:12px;color:#6b7280;margin-top:4px;">Lines Covered</div>
              </td>
              <td width="4%"></td>
              <td width="33%" style="text-align:center;padding:16px;background:#f3f4f6;border-radius:8px;">
                <div style="font-size:36px;font-weight:700;color:#dc2626;">{data["missed_lines"]}</div>
                <div style="font-size:12px;color:#6b7280;margin-top:4px;">Lines Missed</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- Per-package breakdown -->
      <tr>
        <td style="padding:24px 32px 0;">
          <h2 style="font-size:15px;color:#111827;margin:0 0 12px;">Coverage by Module</h2>
          <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;">
            <tr style="background:#f9fafb;">
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#6b7280;font-weight:600;border-bottom:1px solid #e5e7eb;">Module</th>
              <th style="padding:8px 12px;text-align:right;font-size:12px;color:#6b7280;font-weight:600;border-bottom:1px solid #e5e7eb;">Coverage</th>
            </tr>
            {pkg_rows}
          </table>
        </td>
      </tr>

      <!-- CTA -->
      <tr>
        <td style="padding:24px 32px 32px;text-align:center;">
          {f'<a href="{run_url}" style="display:inline-block;background:#1e3a5f;color:#ffffff;text-decoration:none;padding:12px 32px;border-radius:9999px;font-size:14px;font-weight:600;">View Full CI Report →</a>' if run_url else ""}
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;text-align:center;">
          <p style="color:#9ca3af;font-size:12px;margin:0;">Blink Relay · Automated CI Report · Sent every Monday at 9:00 AM UTC</p>
          <p style="color:#9ca3af;font-size:11px;margin:4px 0 0;">© 2026 Blink Charging</p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>
"""


def send_email(args: argparse.Namespace, html: str, total_pct: float) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Blink Relay CI] Weekly Coverage Report — {total_pct}% · {args.branch}"
    msg["From"] = args.smtp_from or args.smtp_user
    msg["To"] = args.to

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(args.smtp_host, int(args.smtp_port)) as server:
        server.ehlo()
        server.starttls()
        server.login(args.smtp_user, args.smtp_pass)
        server.sendmail(msg["From"], [args.to], msg.as_string())

    print(f"Coverage report sent to {args.to} ({total_pct}% coverage)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", required=True, help="Path to coverage.xml")
    parser.add_argument("--smtp-host", required=True)
    parser.add_argument("--smtp-port", default=587)
    parser.add_argument("--smtp-user", required=True)
    parser.add_argument("--smtp-pass", required=True)
    parser.add_argument("--smtp-from", default="")
    parser.add_argument("--to", required=True)
    parser.add_argument("--run-url", default="")
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()

    data = parse_coverage(args.xml)
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    html = build_html(data, args.branch, args.run_url, date_str)
    send_email(args, html, data["total_pct"])


if __name__ == "__main__":
    main()
