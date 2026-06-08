"""
email_group_service.py — Email group management and initialization.

Provides utilities for managing email distribution groups used by
the notification system (e.g., sending to all PMs at once).
"""
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.email_group import EmailGroup, EmailGroupMember
from app.models.request import User

logger = logging.getLogger(__name__)


async def initialize_pm_group(db: AsyncSession) -> EmailGroup:
    """Create or update the PM email group with all current Product Managers.

    - Creates group if it doesn't exist
    - Updates membership to include all active PMs
    - Returns the PM group

    Args:
        db: Async database session

    Returns:
        EmailGroup instance for PMs
    """
    pm_group_name = "Product Managers"
    pm_group_email = "pms@blinkcharging.com"

    # Check if group exists
    result = await db.execute(select(EmailGroup).where(EmailGroup.name == pm_group_name))
    group = result.scalar_one_or_none()

    if not group:
        # Create the group
        group = EmailGroup(
            name=pm_group_name,
            email=pm_group_email,
            description="Distribution list for all Product Managers. Used for system notifications.",
            is_active=True,
        )
        db.add(group)
        await db.flush()
        logger.info(f"Created email group: {pm_group_name}")
    else:
        logger.debug(f"Email group already exists: {pm_group_name}")

    # Get all active PMs
    pm_result = await db.execute(select(User))
    users = pm_result.scalars().all()
    pm_emails = {user.email for user in users if "ProductManager" in user.roles}

    # Remove members who are no longer PMs
    member_result = await db.execute(
        select(EmailGroupMember).where(EmailGroupMember.group_id == group.id)
    )
    members = member_result.scalars().all()
    for member in members:
        if member.user_email not in pm_emails:
            await db.delete(member)
            logger.info(f"Removed {member.user_email} from PM group")

    # Add new PM members
    existing_emails = {m.user_email for m in members}
    for pm_email in pm_emails:
        if pm_email not in existing_emails:
            new_member = EmailGroupMember(group_id=group.id, user_email=pm_email)
            db.add(new_member)
            logger.info(f"Added {pm_email} to PM group")

    await db.commit()
    logger.info(f"PM group now has {len(pm_emails)} members: {', '.join(sorted(pm_emails))}")

    return group


async def get_pm_group_emails(db: AsyncSession) -> tuple[str, list[str]]:
    """Get the PM group email and individual PM email addresses.

    Returns:
        Tuple of (group_email, [individual_pm_emails])
    """
    result = await db.execute(select(EmailGroup).where(EmailGroup.name == "Product Managers"))
    group = result.scalar_one_or_none()

    if not group:
        return None, []

    member_result = await db.execute(
        select(EmailGroupMember).where(EmailGroupMember.group_id == group.id)
    )
    members = member_result.scalars().all()
    pm_emails = [m.user_email for m in members]

    return group.email, pm_emails
