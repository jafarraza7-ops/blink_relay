"""
email_group.py — Email group management for system notifications.

Defines:
  - EmailGroup — Named distribution list for sending emails to groups of users
  - EmailGroupMember — Links users to email groups for bulk notifications
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EmailGroup(Base):
    """Distribution list for sending emails to groups of users.

    Example: PM group for sending notifications to all product managers.
    Stores the group name and email address (e.g., pms@company.com).
    """
    __tablename__ = "email_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Group name (e.g., "Product Managers", "Reviewers")
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    # Group email address (e.g., pms@company.com)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    # Description of the group's purpose
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Whether this group is active
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    members: Mapped[list[EmailGroupMember]] = relationship(
        "EmailGroupMember", back_populates="group", cascade="all, delete-orphan", lazy="select"
    )


class EmailGroupMember(Base):
    """Association between a user and an email group.

    Allows flexible group membership management without changing user data.
    """
    __tablename__ = "email_group_members"
    __table_args__ = (
        UniqueConstraint('group_id', 'user_email', name='unique_group_member'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Email group this member belongs to
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Member's email (allows flexibility if user account is deleted)
    user_email: Mapped[str] = mapped_column(String(254), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    group: Mapped[EmailGroup] = relationship("EmailGroup", back_populates="members")
