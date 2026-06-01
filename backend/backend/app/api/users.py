from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_optional_user
from app.models.request import User

router = APIRouter(tags=["users"])


class UserResponse(BaseModel):
    oid: str
    email: str
    display_name: str

    model_config = {"from_attributes": True}


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    q: Annotated[Optional[str], Query()] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    user: Annotated[Optional[object], Depends(get_optional_user)] = None,
) -> list[UserResponse]:
    """List users for mention autocomplete. Optionally filter by search query."""
    query = select(User).order_by(User.display_name)

    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                User.display_name.ilike(search),
                User.email.ilike(search),
            )
        )

    result = await db.execute(query)
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]
