from __future__ import annotations

import logging
try:
    from enum import StrEnum
except ImportError:  # Python < 3.11
    from enum import Enum
    class StrEnum(str, Enum):
        pass
from functools import lru_cache
from typing import Annotated, Optional

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

bearer_scheme = HTTPBearer(auto_error=True)
optional_bearer_scheme = HTTPBearer(auto_error=False)


class Role(StrEnum):
    REQUESTOR = "Requestor"
    POD_REVIEWER = "PodReviewer"
    PRODUCT_MANAGER = "ProductManager"
    ADMIN = "Admin"
    READ_ONLY = "ReadOnly"


class UserClaims(BaseModel):
    oid: str           # Entra object ID — stable user identifier
    email: str
    name: str
    roles: list[str]
    tid: str           # tenant ID


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch and cache the Entra ID JWKS (JSON Web Key Set).

    The result is cached for the lifetime of the process. In production,
    the cache is invalidated on each cold start (App Service restarts).
    Key rotation is handled gracefully: a JWTError on validation triggers
    a cache clear and a single retry against the live JWKS endpoint.
    """
    jwks_url = (
        f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}"
        f"/discovery/v2.0/keys"
    )
    resp = httpx.get(jwks_url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _clear_jwks_cache() -> None:
    _get_jwks.cache_clear()


def validate_token(token: str) -> dict:
    """Validate a bearer JWT against Entra ID JWKS.

    Returns the decoded claims dict on success.
    Raises HTTP 401 on any validation failure.
    """
    audience = f"api://{settings.AZURE_CLIENT_ID}"
    issuer = f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"

    def _decode(jwks: dict) -> dict:
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"verify_exp": True},
        )

    try:
        return _decode(_get_jwks())
    except JWTError:
        # Key may have rotated — refresh cache and retry once
        _clear_jwks_cache()
        try:
            return _decode(_get_jwks())
        except JWTError as exc:
            logger.warning("JWT validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc


_MOCK_USERS: dict[str, UserClaims] = {
    "admin": UserClaims(
        oid="smoke-test-admin",
        email="admin_dev@ethereal.email",
        name="Dev Admin",
        roles=[Role.ADMIN],
        tid="test-tenant",
    ),
    "pm": UserClaims(
        oid="smoke-test-pm",
        email="pm_dev@ethereal.email",
        name="Dev PM",
        roles=[Role.PRODUCT_MANAGER],
        tid="test-tenant",
    ),
    "requestor": UserClaims(
        oid="smoke-test-requestor",
        email="requestor_dev@ethereal.email",
        name="Dev Requestor",
        roles=[Role.REQUESTOR],
        tid="test-tenant",
    ),
}


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> UserClaims:
    """FastAPI dependency — validates the bearer token and returns user claims."""
    if settings.SKIP_AUTH:
        return _MOCK_USERS.get(settings.SKIP_AUTH_AS, _MOCK_USERS["admin"])

    claims = validate_token(credentials.credentials)

    # Entra ID surfaces group memberships as app roles when configured in the
    # app registration manifest under "appRoles". The claim name is "roles".
    roles: list[str] = claims.get("roles", [])

    # Fallback: every authenticated Entra user is at minimum a Requestor
    if not roles:
        roles = [Role.REQUESTOR]

    email = claims.get("preferred_username") or claims.get("upn") or claims.get("email", "")

    return UserClaims(
        oid=claims["oid"],
        email=email,
        name=claims.get("name", email),
        roles=roles,
        tid=claims.get("tid", ""),
    )


def get_optional_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Security(optional_bearer_scheme),
    ],
) -> Optional[UserClaims]:
    """FastAPI dependency — returns UserClaims if a valid token is present, else None."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None


def require_role(*allowed_roles: Role):
    """FastAPI dependency factory — raises 403 if the user lacks the required role."""

    def _dependency(user: Annotated[UserClaims, Depends(get_current_user)]) -> UserClaims:
        if Role.ADMIN in user.roles:
            return user  # admins bypass all role checks
        for role in allowed_roles:
            if role in user.roles:
                return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required role(s): {[r.value for r in allowed_roles]}",
        )

    return _dependency
