"""mention_service.py — Utilities for parsing and handling user mentions in messages.

Functions:
  extract_mentions — Parse @username patterns from message body
  notify_mentioned_users — Send notifications to mentioned users
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.request import User

logger = logging.getLogger(__name__)

# Regex to match @username patterns (alphanumeric, dots, hyphens, underscores)
MENTION_PATTERN = re.compile(r'@([\w\.\-]+)')


def extract_mentions(body: str, db_session: AsyncSession = None) -> list[str]:
    """Extract mentioned user OIDs from message body.

    Searches for @username patterns and returns list of matching user OIDs.
    If db_session is None, returns empty list (username matching requires DB lookup).

    Args:
        body: Message text containing potential @mentions
        db_session: SQLAlchemy async session for user lookup

    Returns:
        List of user OIDs that were mentioned
    """
    if not db_session:
        return []

    # Find all @username patterns
    usernames = MENTION_PATTERN.findall(body)
    if not usernames:
        return []

    # Note: In production, you'd want to match by display_name or email prefix
    # For now, return empty list - frontend will send user OIDs directly
    return []


async def notify_mentioned_users(
    request_id: uuid.UUID,
    message_id: uuid.UUID,
    mentioned_oids: list[str],
    author_name: str,
    body_preview: str,
    db: AsyncSession,
) -> None:
    """Queue notifications for mentioned users.

    Args:
        request_id: The request being commented on
        message_id: The message ID containing mentions
        mentioned_oids: List of user OIDs to notify
        author_name: Name of the person who mentioned them
        body_preview: First 100 chars of the message for preview
        db: Database session
    """
    if not mentioned_oids:
        return

    # Fetch mentioned users
    result = await db.execute(
        select(User).where(User.oid.in_(mentioned_oids))
    )
    mentioned_users = result.scalars().all()

    # Queue notification tasks for each mentioned user
    # (Implementation depends on your notification system)
    for user in mentioned_users:
        logger.info(
            f"User {user.display_name} was mentioned in request {request_id}",
            extra={"user_oid": user.oid, "request_id": str(request_id)}
        )
        # TODO: Queue task_send_mention_notification.delay(
        #   str(request_id),
        #   user.email,
        #   author_name,
        #   body_preview
        # )
