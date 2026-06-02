"""email_service.py — Email templates for authentication and notifications."""
from __future__ import annotations


def get_request_creation_template(reference_id: str, title: str, request_type: str, priority: str, user_name: str, request_url: str) -> str:
    """Generate HTML email template for request creation confirmation.

    Args:
        reference_id: Request reference ID (e.g., BLR-2026-0001)
        title: Request title
        request_type: Type of request (Feature or Defect)
        priority: Priority level (Critical, High, Medium, Low)
        user_name: Name of the requestor
        request_url: URL to view the request

    Returns:
        HTML email content
    """
    priority_color = {
        "CRITICAL": "#dc2626",
        "HIGH": "#ea580c",
        "MEDIUM": "#eab308",
        "LOW": "#16a34a",
    }.get(priority, "#6b7280")

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f9fafb;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .email-box {{
            background: white;
            border-radius: 8px;
            padding: 40px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            display: flex;
            align-items: center;
            margin-bottom: 30px;
        }}
        .logo {{
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #0066cc 0%, #004499 100%);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            margin-right: 10px;
        }}
        .brand {{
            color: #0066cc;
            font-size: 16px;
            font-weight: 600;
        }}
        h2 {{
            color: #111827;
            margin: 0 0 10px 0;
            font-size: 24px;
        }}
        p {{
            color: #4b5563;
            font-size: 14px;
            line-height: 1.6;
            margin: 15px 0;
        }}
        .cta-button {{
            display: inline-block;
            background: linear-gradient(135deg, #0066cc 0%, #004499 100%);
            color: white;
            padding: 12px 24px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            margin: 20px 0;
            transition: opacity 0.2s;
        }}
        .cta-button:hover {{
            opacity: 0.9;
        }}
        .details-box {{
            background: #f3f4f6;
            border-left: 4px solid #0066cc;
            padding: 16px;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .detail-row {{
            display: flex;
            margin-bottom: 12px;
            align-items: center;
        }}
        .detail-label {{
            font-weight: 600;
            color: #374151;
            width: 100px;
        }}
        .detail-value {{
            color: #4b5563;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            color: white;
            background-color: {priority_color};
        }}
        .footer {{
            color: #9ca3af;
            font-size: 12px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-box">
            <div class="header">
                <div class="logo">⚡</div>
                <div class="brand">Blink Relay</div>
            </div>

            <h2>Request Submitted Successfully</h2>

            <p>Hi {user_name},</p>

            <p>Your request has been successfully submitted to Blink Relay and is now in the review queue. Our team will review it shortly and keep you updated on the progress.</p>

            <div class="details-box">
                <div class="detail-row">
                    <div class="detail-label">Reference ID:</div>
                    <div class="detail-value"><strong>{reference_id}</strong></div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Title:</div>
                    <div class="detail-value">{title}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Type:</div>
                    <div class="detail-value">{request_type}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Priority:</div>
                    <div class="detail-value"><span class="badge">{priority}</span></div>
                </div>
            </div>

            <center>
                <a href="{request_url}" class="cta-button">View Your Request</a>
            </center>

            <p>You'll receive email updates as your request progresses through the review workflow. If you have any questions, please reach out to the Blink team.</p>

            <div class="footer">
                <p>Blink Relay • Product Intake System</p>
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>© 2026 Blink Charging. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>"""


def get_email_login_template(login_url: str, user_name: str = "Requestor") -> str:
    """Generate HTML email template for magic link login.
    
    Args:
        login_url: Full URL with token for the user to click
        user_name: Name to greet the user (defaults to "Requestor" for new users)
        
    Returns:
        HTML email content
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f9fafb;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .email-box {{
            background: white;
            border-radius: 8px;
            padding: 40px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            display: flex;
            align-items: center;
            margin-bottom: 30px;
        }}
        .logo {{
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #0066cc 0%, #004499 100%);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            margin-right: 10px;
        }}
        .brand {{
            color: #0066cc;
            font-size: 16px;
            font-weight: 600;
        }}
        h2 {{
            color: #111827;
            margin: 0 0 10px 0;
            font-size: 24px;
        }}
        p {{
            color: #4b5563;
            font-size: 14px;
            line-height: 1.6;
            margin: 15px 0;
        }}
        .cta-button {{
            display: inline-block;
            background: linear-gradient(135deg, #0066cc 0%, #004499 100%);
            color: white;
            padding: 12px 24px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            margin: 20px 0;
            transition: opacity 0.2s;
        }}
        .cta-button:hover {{
            opacity: 0.9;
        }}
        .warning {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 12px 16px;
            border-radius: 4px;
            margin: 20px 0;
            font-size: 13px;
            color: #92400e;
        }}
        .footer {{
            color: #9ca3af;
            font-size: 12px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
        }}
        .code {{
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-box">
            <div class="header">
                <div class="logo">⚡</div>
                <div class="brand">Blink Relay</div>
            </div>
            
            <h2>Log in to Blink Relay</h2>
            
            <p>Hi {user_name},</p>
            
            <p>You requested a login link for Blink Relay. Click the button below to log in:</p>
            
            <center>
                <a href="{login_url}" class="cta-button">Log in to Blink Relay</a>
            </center>
            
            <p>Or copy and paste this link into your browser:</p>
            <p><code class="code">{login_url}</code></p>
            
            <div class="warning">
                <strong>⏰ Link expires in 15 minutes.</strong> This is a one-time use link.
            </div>
            
            <div class="warning">
                <strong>🔒 Didn't request this email?</strong> You can safely ignore it. Your account is secure.
            </div>
            
            <div class="footer">
                <p>Blink Relay • Product Intake System</p>
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>© 2026 Blink Charging. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>"""
