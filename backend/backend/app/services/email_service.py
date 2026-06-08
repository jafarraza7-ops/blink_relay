"""email_service.py — Email templates for authentication and notifications."""
from __future__ import annotations


def get_status_update_template(reference_id: str, title: str, old_status: str, new_status: str, user_name: str, request_url: str) -> str:
    """Request status update notification email."""
    status_color = {
        "SUBMITTED": "#3b82f6",
        "IN_REVIEW": "#f59e0b",
        "AWAITING_INFO": "#ef4444",
        "APPROVED": "#10b981",
        "IN_PROGRESS": "#8b5cf6",
        "COMPLETED": "#10b981",
        "REJECTED": "#ef4444",
    }.get(new_status, "#6b7280")

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .email-box {{ background: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); }}
        .header {{ display: flex; align-items: center; margin-bottom: 30px; }}
        .logo {{ width: 32px; height: 32px; background: linear-gradient(135deg, #0066cc 0%, #004499 100%); border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 10px; }}
        .brand {{ color: #0066cc; font-size: 16px; font-weight: 600; }}
        h2 {{ color: #111827; margin: 0 0 10px 0; font-size: 24px; }}
        p {{ color: #4b5563; font-size: 14px; line-height: 1.6; margin: 15px 0; }}
        .cta-button {{ display: inline-block; background: linear-gradient(135deg, #0066cc 0%, #004499 100%); color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 20px 0; transition: opacity 0.2s; }}
        .cta-button:hover {{ opacity: 0.9; }}
        .status-box {{ background: #f3f4f6; border-left: 4px solid {status_color}; padding: 16px; border-radius: 4px; margin: 20px 0; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; color: white; background-color: {status_color}; }}
        .footer {{ color: #9ca3af; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-box">
            <div class="header">
                <div class="logo">⚡</div>
                <div class="brand">Blink Relay</div>
            </div>
            <h2>Request Status Updated</h2>
            <p>Hi {user_name},</p>
            <p>The status of your request has been updated:</p>
            <div class="status-box">
                <p><strong>{reference_id}</strong></p>
                <p>{title}</p>
                <p>Status: <span class="badge">{new_status}</span></p>
            </div>
            <center>
                <a href="{request_url}" class="cta-button">View Request</a>
            </center>
            <div class="footer">
                <p>Blink Relay • Product Intake System</p>
                <p>© 2026 Blink Charging. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>"""


def get_new_message_template(reference_id: str, title: str, author_name: str, message_preview: str, user_name: str, request_url: str) -> str:
    """New conversation message notification email."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .email-box {{ background: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); }}
        .header {{ display: flex; align-items: center; margin-bottom: 30px; }}
        .logo {{ width: 32px; height: 32px; background: linear-gradient(135deg, #0066cc 0%, #004499 100%); border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 10px; }}
        .brand {{ color: #0066cc; font-size: 16px; font-weight: 600; }}
        h2 {{ color: #111827; margin: 0 0 10px 0; font-size: 24px; }}
        p {{ color: #4b5563; font-size: 14px; line-height: 1.6; margin: 15px 0; }}
        .cta-button {{ display: inline-block; background: linear-gradient(135deg, #0066cc 0%, #004499 100%); color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 20px 0; transition: opacity 0.2s; }}
        .cta-button:hover {{ opacity: 0.9; }}
        .message-box {{ background: #f3f4f6; border-left: 4px solid #0066cc; padding: 16px; border-radius: 4px; margin: 20px 0; }}
        .author {{ font-weight: 600; color: #374151; margin-bottom: 8px; }}
        .preview {{ color: #4b5563; font-style: italic; }}
        .footer {{ color: #9ca3af; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-box">
            <div class="header">
                <div class="logo">⚡</div>
                <div class="brand">Blink Relay</div>
            </div>
            <h2>New Message on Your Request</h2>
            <p>Hi {user_name},</p>
            <p>There's a new message on request <strong>{reference_id}</strong>:</p>
            <div class="message-box">
                <div class="author">From: {author_name}</div>
                <div class="preview">"{message_preview}"</div>
            </div>
            <center>
                <a href="{request_url}" class="cta-button">View Conversation</a>
            </center>
            <div class="footer">
                <p>Blink Relay • Product Intake System</p>
                <p>© 2026 Blink Charging. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>"""


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

def get_request_cancellation_template(reference_id: str, title: str, submitted_by: str, cancellation_date: str) -> str:
    """Request cancellation notification email."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .email-box {{ background: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); }}
        .header {{ display: flex; align-items: center; margin-bottom: 30px; }}
        .logo {{ width: 32px; height: 32px; background: linear-gradient(135deg, #0066cc 0%, #004499 100%); border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 10px; }}
        .brand {{ color: #0066cc; font-size: 16px; font-weight: 600; }}
        h2 {{ color: #111827; margin: 0 0 10px 0; font-size: 24px; }}
        p {{ color: #4b5563; font-size: 14px; line-height: 1.6; margin: 15px 0; }}
        .cancellation-box {{ background: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; border-radius: 4px; margin: 20px 0; }}
        .detail-row {{ display: flex; justify-content: space-between; margin: 8px 0; padding: 8px 0; }}
        .detail-label {{ font-weight: 600; color: #111827; }}
        .detail-value {{ color: #4b5563; }}
        .status-badge {{ display: inline-block; padding: 6px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; color: white; background-color: #ef4444; }}
        .footer {{ color: #9ca3af; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-box">
            <div class="header">
                <div class="logo">⚡</div>
                <div class="brand">Blink Relay</div>
            </div>
            <h2>Request Cancelled</h2>
            <p>Hi,</p>
            <p>A request has been cancelled and we wanted to notify you:</p>
            <div class="cancellation-box">
                <div class="detail-row">
                    <span class="detail-label">Reference ID:</span>
                    <span class="detail-value"><strong>{reference_id}</strong></span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Title:</span>
                    <span class="detail-value">{title}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Cancelled by:</span>
                    <span class="detail-value">{submitted_by}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Date:</span>
                    <span class="detail-value">{cancellation_date}</span>
                </div>
                <div style="margin-top: 12px;">
                    <span class="status-badge">CANCELLED</span>
                </div>
            </div>
            <p>This request is no longer being processed. If you have any questions, please reach out to the request submitter or your team lead.</p>
            <div class="footer">
                <p>Blink Relay • Product Intake System</p>
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>© 2026 Blink Charging. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>"""


def get_pending_reminder_template(reference_id: str, title: str, submitter_name: str, created_at: str) -> str:
    """Email template for PM reminder about request pending review for 72+ hours.

    Sent once every 24 hours to all PMs when a request remains in SUBMITTED or IN_REVIEW
    status without status update for 72+ hours, encouraging them to review and update status.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .email-box {{ background: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); }}
        .header {{ display: flex; align-items: center; margin-bottom: 30px; }}
        .logo {{ width: 32px; height: 32px; background: linear-gradient(135deg, #0066cc 0%, #004499 100%); border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 10px; }}
        .brand {{ color: #0066cc; font-size: 16px; font-weight: 600; }}
        h2 {{ color: #111827; margin: 0 0 10px 0; font-size: 24px; }}
        p {{ color: #4b5563; font-size: 14px; line-height: 1.6; margin: 15px 0; }}
        .cta-button {{ display: inline-block; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 20px 0; transition: opacity 0.2s; }}
        .cta-button:hover {{ opacity: 0.9; }}
        .alert-box {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; border-radius: 4px; margin: 20px 0; }}
        .alert-box .alert-title {{ font-weight: 700; color: #d97706; margin-bottom: 8px; }}
        .alert-box p {{ margin: 4px 0; color: #78350f; }}
        .request-details {{ background: #f3f4f6; padding: 16px; border-radius: 4px; margin: 20px 0; }}
        .detail-row {{ display: flex; justify-content: space-between; margin: 8px 0; font-size: 13px; }}
        .detail-label {{ font-weight: 600; color: #374151; min-width: 100px; }}
        .detail-value {{ color: #4b5563; flex: 1; }}
        .footer {{ color: #9ca3af; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-box">
            <div class="header">
                <div class="logo">⚡</div>
                <div class="brand">Blink Relay</div>
            </div>
            <h2>Action Required: Pending Request Review</h2>
            <p>Hi Product Manager,</p>
            <div class="alert-box">
                <div class="alert-title">Request pending for 72+ hours</div>
                <p>Request <strong>{reference_id}</strong> from {submitter_name} has been waiting for review or status update.</p>
                <p>Please review and update the status to keep stakeholders informed.</p>
            </div>
            <div class="request-details">
                <div class="detail-row">
                    <span class="detail-label">Reference ID:</span>
                    <span class="detail-value"><strong>{reference_id}</strong></span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Title:</span>
                    <span class="detail-value">{title}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Submitted:</span>
                    <span class="detail-value">{created_at}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Submitted by:</span>
                    <span class="detail-value">{submitter_name}</span>
                </div>
            </div>
            <p>Timely feedback helps maintain stakeholder confidence and ensures requests are prioritized appropriately.</p>
            <center>
                <a href="https://blink-relay.example.com/requests/{reference_id}" class="cta-button">Review Request</a>
            </center>
            <div class="footer">
                <p>Blink Relay • Product Intake System</p>
                <p>This is an automated reminder. Requests are auto-reminding PMs when pending for 72+ hours.</p>
                <p>© 2026 Blink Charging. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>"""


def get_claim_notification_template(reference_id: str, title: str, pm_name: str, priority: str) -> str:
    """Email template when a PM claims a request.

    Notifies other team members that a PM is working on this request.
    """
    priority_color = {
        "Critical": "#ef4444",
        "High": "#f97316",
        "Medium": "#f59e0b",
        "Low": "#84cc16",
    }.get(priority, "#6b7280")

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .email-box {{ background: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); }}
        .header {{ display: flex; align-items: center; margin-bottom: 30px; }}
        .logo {{ width: 32px; height: 32px; background: linear-gradient(135deg, #0066cc 0%, #004499 100%); border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 10px; }}
        .brand {{ color: #0066cc; font-size: 16px; font-weight: 600; }}
        h2 {{ color: #111827; margin: 0 0 10px 0; font-size: 24px; }}
        p {{ color: #4b5563; font-size: 14px; line-height: 1.6; margin: 15px 0; }}
        .info-box {{ background: #f0f9ff; border-left: 4px solid #0066cc; padding: 16px; border-radius: 4px; margin: 20px 0; }}
        .pm-name {{ font-size: 16px; font-weight: 600; color: #0066cc; margin: 10px 0; }}
        .priority-badge {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; color: white; background-color: {priority_color}; }}
        .footer {{ color: #9ca3af; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-box">
            <div class="header">
                <div class="logo">⚡</div>
                <div class="brand">Blink Relay</div>
            </div>
            <h2>Request Claimed</h2>
            <p>Hi there,</p>
            <p><strong>{pm_name}</strong> is now working on the following request:</p>
            <div class="info-box">
                <p><strong>{reference_id}</strong></p>
                <p>{title}</p>
                <p>Priority: <span class="priority-badge">{priority}</span></p>
            </div>
            <p>Please coordinate with <strong>{pm_name}</strong> if you also need to work on this request to avoid duplicate effort.</p>
            <div class="footer">
                <p>Blink Relay • Product Intake System</p>
                <p>© 2026 Blink Charging. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>"""


def get_unclaim_notification_template(reference_id: str, title: str, pm_name: str) -> str:
    """Email template when a PM releases a claimed request.

    Notifies team members that a request is available to work on.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .email-box {{ background: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); }}
        .header {{ display: flex; align-items: center; margin-bottom: 30px; }}
        .logo {{ width: 32px; height: 32px; background: linear-gradient(135deg, #0066cc 0%, #004499 100%); border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 10px; }}
        .brand {{ color: #0066cc; font-size: 16px; font-weight: 600; }}
        h2 {{ color: #111827; margin: 0 0 10px 0; font-size: 24px; }}
        p {{ color: #4b5563; font-size: 14px; line-height: 1.6; margin: 15px 0; }}
        .info-box {{ background: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; border-radius: 4px; margin: 20px 0; }}
        .footer {{ color: #9ca3af; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-box">
            <div class="header">
                <div class="logo">⚡</div>
                <div class="brand">Blink Relay</div>
            </div>
            <h2>Request Available</h2>
            <p>Hi there,</p>
            <p><strong>{pm_name}</strong> has released their claim on the following request:</p>
            <div class="info-box">
                <p><strong>{reference_id}</strong></p>
                <p>{title}</p>
            </div>
            <p>This request is now available for other team members to work on. Please coordinate within the team to determine who will take it next.</p>
            <div class="footer">
                <p>Blink Relay • Product Intake System</p>
                <p>© 2026 Blink Charging. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>"""
