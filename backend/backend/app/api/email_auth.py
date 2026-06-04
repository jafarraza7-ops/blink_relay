"""email_auth.py — Email-based authentication endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import generate_jwt_token
from app.models.request import User, EmailLoginToken
from app.services.token_service import (
    create_login_token,
    validate_token,
    get_or_create_email_user,
)
from app.services.email_service import get_email_login_template
from app.workers.email_tasks import task_send_email_login_link

router = APIRouter(tags=["email_auth"], prefix="/auth/email")


class EmailLoginRequest(BaseModel):
    email: EmailStr


class TokenVerifyRequest(BaseModel):
    token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    roles: list[str]


class TokenVerifyResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class TokenStatusResponse(BaseModel):
    valid: bool
    reason: str | None


@router.post("/request-login", status_code=202)
async def request_login(
    payload: EmailLoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Request a magic link login email.
    
    Always returns 202 regardless of whether email exists (prevents enumeration).
    Generates token, saves to DB, and queues email send task.
    
    Rate limiting: Max 3 requests per IP per hour (implement in production).
    """
    email = payload.email
    ip_address = request.client.host if request.client else "unknown"
    
    # Generate token and save to DB
    plaintext_token, token_record = await create_login_token(db, email, ip_address)
    await db.commit()
    
    # Get frontend URL for the callback link
    from app.core.config import get_settings
    settings = get_settings()
    login_url = f"{settings.FRONTEND_URL}/auth/email/callback?token={plaintext_token}"
    
    # Queue email send task (non-blocking)
    task_send_email_login_link.delay(email, login_url, email)
    
    return {
        "message": "Check your email for a login link",
        "email": email,
    }


@router.post("/verify-token", response_model=TokenVerifyResponse, status_code=200)
async def verify_token(
    payload: TokenVerifyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Validate token and complete login.
    
    - Checks token validity, expiration, and one-time-use
    - Creates user if first login
    - Returns JWT session token
    - Returns 400 for invalid/expired/used tokens (no info leak)
    """
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Validate token
    token_record, error = await validate_token(db, payload.token, ip_address, user_agent)

    if error:
        raise HTTPException(status_code=400, detail=error)

    # Explicitly update the token record using a direct query
    from datetime import datetime, timezone
    from sqlalchemy import update

    await db.execute(
        update(EmailLoginToken).where(EmailLoginToken.id == token_record.id).values(
            is_used=True,
            used_at=datetime.now(timezone.utc),
            used_ip_address=ip_address,
            used_user_agent=user_agent,
        )
    )

    # Get or create user
    user = await get_or_create_email_user(db, token_record.email)

    # Update user with verified email and last login info
    user.email_verified = True
    user.last_login_method = "email"
    user.last_seen_at = datetime.now(timezone.utc)

    await db.commit()
    
    # Generate JWT
    access_token = generate_jwt_token(user)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.display_name,
            roles=user.roles,
        ),
    }


@router.post("/resend-token", status_code=202)
async def resend_token(
    payload: EmailLoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Resend a login link to the user's email.
    
    Invalidates previous tokens for this email and generates a new one.
    Rate limited: Same as request-login (3 per IP per hour).
    """
    email = payload.email
    ip_address = request.client.host if request.client else "unknown"
    
    # Generate new token (old ones are automatically invalidated)
    plaintext_token, token_record = await create_login_token(db, email, ip_address)
    await db.commit()
    
    # Queue email send task
    from app.core.config import get_settings
    settings = get_settings()
    login_url = f"{settings.FRONTEND_URL}/auth/email/callback?token={plaintext_token}"
    
    task_send_email_login_link.delay(email, login_url, email)
    
    return {
        "message": "Check your email for a new login link",
        "email": email,
    }


@router.get("/login-status/{token}", response_model=TokenStatusResponse)
async def check_token_status(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Check if a token is valid (used by frontend during callback).
    
    Returns whether the token can be used to complete login.
    Used to show user status before they submit the token.
    """
    from app.services.token_service import hash_token
    from sqlalchemy import select
    from app.models.request import EmailLoginToken
    
    token_hash = hash_token(token)
    
    result = await db.execute(
        select(EmailLoginToken).where(EmailLoginToken.token_hash == token_hash)
    )
    token_record = result.scalar_one_or_none()
    
    # Token not found
    if not token_record:
        return TokenStatusResponse(valid=False, reason="Invalid or expired token")
    
    # Already used
    if token_record.is_used:
        return TokenStatusResponse(valid=False, reason="Token already used")
    
    # Already invalidated
    if token_record.invalidated_at is not None:
        return TokenStatusResponse(valid=False, reason="Token expired or invalid")
    
    # Expired
    from datetime import datetime, timezone
    if datetime.now(timezone.utc) > token_record.expires_at:
        return TokenStatusResponse(valid=False, reason="Link expired")

    # Valid
    return TokenStatusResponse(valid=True, reason=None)


@router.post("/dev/get-token", status_code=200)
async def dev_get_token(
    payload: EmailLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """DEV ONLY: Generate a test token and return the plaintext for testing.

    This endpoint allows testing the email login flow without an email provider.
    Remove this endpoint before deploying to production.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.is_local:
        raise HTTPException(status_code=403, detail="Not available in production")

    email = payload.email
    plaintext_token, token_record = await create_login_token(db, email, "127.0.0.1")
    await db.commit()

    settings = get_settings()
    callback_url = f"{settings.FRONTEND_URL}/auth/email/callback?token={plaintext_token}"

    return {
        "email": email,
        "token": plaintext_token,
        "callback_url": callback_url,
        "expires_in_minutes": 15,
    }
