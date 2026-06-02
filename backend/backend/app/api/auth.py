from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import UserClaims, get_current_user
from app.models.request import User

router = APIRouter(tags=["auth"])


class MeResponse(BaseModel):
    oid: Optional[str]  # None for email-authenticated users
    email: str
    name: str
    roles: list[str]


@router.get("/auth/me", response_model=MeResponse)
async def get_me(user: Annotated[UserClaims, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(oid=user.oid, email=user.email, name=user.name, roles=user.roles)


@router.post("/auth/sync", response_model=MeResponse)
async def sync_user(
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeResponse:
    """Upsert the authenticated user record into the local users table."""
    from datetime import datetime, timezone

    # Look up by oid (Azure AD) or email (email auth)
    if user.oid:
        result = await db.execute(select(User).where(User.oid == user.oid))
    else:
        result = await db.execute(select(User).where(User.email == user.email))

    db_user = result.scalar_one_or_none()

    if db_user:
        db_user.email = user.email
        db_user.display_name = user.name
        db_user.roles = user.roles
        db_user.last_seen_at = datetime.now(timezone.utc)
    else:
        db_user = User(
            oid=user.oid,
            email=user.email,
            display_name=user.name,
            roles=user.roles,
        )
        db.add(db_user)

    await db.flush()
    return MeResponse(oid=user.oid, email=user.email, name=user.name, roles=user.roles)
