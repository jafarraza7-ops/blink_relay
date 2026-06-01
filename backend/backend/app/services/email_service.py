"""email_service.py — Email template and utilities for authentication."""
from __future__ import annotations


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
