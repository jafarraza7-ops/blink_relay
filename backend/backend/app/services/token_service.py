"""token_service.py — Secure email login token generation and validation."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import EmailLoginToken, User

TOKEN_EXPIRY_MINUTES = 60
TOKEN_LENGTH_BYTES = 32  # 256 bits


def generate_token() -> str:
    """Generate a cryptographically secure token (base64-encoded 256 bits)."""
    return secrets.token_urlsafe(TOKEN_LENGTH_BYTES)


def hash_token(plaintext: str) -> str:
    """Hash token using SHA-256 for storage."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


async def create_login_token(
    db: AsyncSession,
    email: str,
    ip_address: str,
) -> tuple[str, EmailLoginToken]:
    """Create a new email login token.
    
    Invalidates any previous unused tokens for this email.
    
    Args:
        db: Async database session
        email: User email (will be normalized to lowercase)
        ip_address: IP address of the request for audit
        
    Returns:
        (plaintext_token, token_record)
    """
    email_normalized = email.lower()
    
    # Invalidate all previous unused tokens for this email
    previous_tokens = await db.execute(
        select(EmailLoginToken).where(
            and_(
                EmailLoginToken.email == email_normalized,
                EmailLoginToken.is_used == False,  # noqa: E712
                EmailLoginToken.invalidated_at.is_(None),
            )
        )
    )
    for token in previous_tokens.scalars().all():
        token.is_used = True
        token.invalidation_reason = "superseded"
        token.invalidated_at = datetime.now(timezone.utc)
    
    # Generate new token
    plaintext_token = generate_token()
    token_hash = hash_token(plaintext_token)
    
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
    
    token_record = EmailLoginToken(
        email=email_normalized,
        token_hash=token_hash,
        is_used=False,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        request_ip_address=ip_address,
    )
    
    db.add(token_record)
    await db.flush()
    
    return plaintext_token, token_record


async def validate_token(
    db: AsyncSession,
    plaintext_token: str,
    ip_address: str,
    user_agent: str,
) -> tuple[Optional[EmailLoginToken], Optional[str]]:
    """Validate an email login token.
    
    Args:
        db: Async database session
        plaintext_token: The token from the user
        ip_address: IP address for audit
        user_agent: User agent for audit
        
    Returns:
        (token_record, error_message)
        - On success: (EmailLoginToken, None)
        - On failure: (None, user-safe error message)
    """
    token_hash = hash_token(plaintext_token)
    
    result = await db.execute(
        select(EmailLoginToken).where(EmailLoginToken.token_hash == token_hash)
    )
    token_record = result.scalar_one_or_none()
    
    # Token not found — don't reveal whether it ever existed
    if not token_record:
        return None, "Invalid or expired token"
    
    # Check if already used
    if token_record.is_used:
        return None, "Invalid or expired token"
    
    # Check if invalidated (e.g., superseded by newer token)
    if token_record.invalidated_at is not None:
        return None, "Invalid or expired token"
    
    # Check if expired (convert expires_at to UTC-aware for comparison)
    expires_at_utc = token_record.expires_at.replace(tzinfo=timezone.utc) if token_record.expires_at.tzinfo is None else token_record.expires_at
    if datetime.now(timezone.utc) > expires_at_utc:
        token_record.invalidation_reason = "expired"
        token_record.invalidated_at = datetime.now(timezone.utc)
        await db.flush()
        return None, "Invalid or expired token"
    
    # Mark as used (atomic operation)
    token_record.is_used = True
    token_record.used_at = datetime.now(timezone.utc)
    token_record.used_ip_address = ip_address
    token_record.used_user_agent = user_agent
    
    return token_record, None


async def check_and_update_lockout(db: AsyncSession, email: str) -> tuple[bool, Optional[str]]:
    """Check if account is locked and update failed attempts.
    
    Returns:
        (is_locked, error_message) tuple
    """
    from app.models.request import User
    
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar()
    
    if not user:
        return False, None
    
    now = datetime.now(timezone.utc)
    
    # Check if account is currently locked
    if user.locked_until and user.locked_until > now:
        remaining_minutes = int((user.locked_until - now).total_seconds() / 60)
        return True, f"Account locked. Try again in {remaining_minutes} minutes."
    
    # If lock has expired, reset failed attempts
    if user.locked_until and user.locked_until <= now:
        user.locked_until = None
        user.failed_login_attempts = 0
        db.add(user)
        await db.flush()
    
    return False, None


async def increment_failed_attempts(db: AsyncSession, email: str) -> None:
    """Increment failed login attempts and lock account if needed."""
    from app.models.request import User
    
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar()
    
    if not user:
        return
    
    user.failed_login_attempts += 1
    
    # Lock account after 5 failed attempts for 15 minutes
    if user.failed_login_attempts >= 5:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    db.add(user)
    await db.flush()


async def reset_failed_attempts(db: AsyncSession, email: str) -> None:
    """Reset failed attempts on successful login."""
    from app.models.request import User
    
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar()
    
    if user:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.add(user)
        await db.flush()


async def get_or_create_email_user(
    db: AsyncSession,
    email: str,
) -> User:
    """Get existing user or create a new one for email login.
    
    Args:
        db: Async database session
        email: User email (will be normalized)
        
    Returns:
        User object (existing or newly created)
    """
    email_normalized = email.lower()
    
    result = await db.execute(
        select(User).where(User.email == email_normalized)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Existing user — update auth_source if needed
        if user.auth_source is None or user.auth_source == "azure_ad":
            user.auth_source = "email"
        return user
    
    # Create new user for first-time email login
    from app.core.security import Role
    
    user = User(
        oid=None,  # No Azure AD OID for email users
        email=email_normalized,
        display_name=email_normalized.split("@")[0].replace(".", " ").title(),
        roles=[Role.REQUESTOR],
        auth_source="email",
        email_verified=True,
    )
    db.add(user)
    await db.flush()
    
    return user
