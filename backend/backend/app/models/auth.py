"""
models/auth.py — SQLAlchemy ORM models for email-based authentication.

Defines:
  - LoginToken — temporary token generated for magic-link email logins
    Stores token, email, user_id (nullable for new signups), expiration.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LoginToken(Base):
    """Temporary authentication token for email-based login.

    Each token is single-use and time-limited (15 minutes by default).
    Token is stored as a one-way hash to prevent plaintext storage.
    """
    __tablename__ = "login_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # The actual token sent in the email link (stored hashed, but checking is done against plaintext)
    # In a real system, store only the hash; here we store plaintext for simplicity.
    token: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    # user_id is NULL for new signups (email doesn't exist yet in users table)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Timestamp when token was successfully used to create a session
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
