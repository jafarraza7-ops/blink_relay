"""
core/security.py — Authentication and authorisation for Blink Relay.

Auth flow:
  1. The React SPA acquires a bearer JWT from Microsoft Entra ID (MSAL).
  2. Every protected API endpoint receives the token in the Authorization header.
  3. get_current_user() validates the JWT against Entra's public JWKS endpoint,
     extracts the user's roles (app roles configured in the Entra app manifest),
     and returns a UserClaims object used as a FastAPI dependency.

Local dev bypass:
  Set SKIP_AUTH=true in the environment to skip JWT validation entirely. Use
  SKIP_AUTH_AS=pm|admin|requestor to impersonate a built-in mock user. The
  dependency still uses optional_bearer_scheme (auto_error=False) so the
  endpoint body is always reached even when no token is present.

Role hierarchy:
  Admin > ProductManager / PodReviewer > Requestor (read-only).
  require_role() enforces this; Admins bypass all role checks.
"""
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

# ── Bearer schemes ────────────────────────────────────────────────────────────

# bearer_scheme raises 401 immediately if the header is missing (strict endpoints).
bearer_scheme = HTTPBearer(auto_error=True)
# optional_bearer_scheme lets the request through even with no token; the
# dependency function decides what to do (used for SKIP_AUTH and public routes).
optional_bearer_scheme = HTTPBearer(auto_error=False)


# ── Domain models ─────────────────────────────────────────────────────────────

class Role(StrEnum):
    """Application roles assigned to users in the Entra app registration manifest."""
    REQUESTOR = "Requestor"
    POD_REVIEWER = "PodReviewer"
    PRODUCT_MANAGER = "ProductManager"
    ADMIN = "Admin"
    READ_ONLY = "ReadOnly"


def validate_user_roles(roles: list[str]) -> list[str]:
    """Validate and normalize user roles.

    FEATURE: Allow PMs to be Requestors (removed mutual exclusivity)
    Reasoning: PMs should be able to create their own requests and receive email notifications.
    Previous behavior: ProductManager role automatically removed Requestor role.
    Current behavior: Both roles can coexist for the same user.

    Args:
        roles: List of role strings assigned to user

    Returns:
        Validated list of roles (unchanged - no role filtering applied)
    """
    if not roles:
        return roles
    return roles


class UserClaims(BaseModel):
    oid: Optional[str] # Entra object ID — stable user identifier (None for email users)
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


# ── JWKS helpers ──────────────────────────────────────────────────────────────

# ── Local-dev mock users ───────────────────────────────────────────────────────

# Pre-built user fixtures used when SKIP_AUTH=true. Ethereal addresses are
# throw-away inboxes so notification emails are safe to send in dev.
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
        oid="jraza-requestor-oid",
        email="jraza.requestor@blinkcharging.com",
        name="Jafar Raza (Requestor)",
        roles=[Role.REQUESTOR],
        tid="test-tenant",
    ),
}


# ── FastAPI dependencies ───────────────────────────────────────────────────────

def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Security(optional_bearer_scheme),
    ],
) -> UserClaims:
    """FastAPI dependency — validates the bearer token and returns user claims."""
    _s = get_settings()
    if _s.SKIP_AUTH:
        return _MOCK_USERS.get(_s.SKIP_AUTH_AS, _MOCK_USERS["admin"])

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    logger.debug("Validating token (first 20 chars): %s...", token[:20] if len(token) > 20 else token)

    # Try email JWT (HS256) first, then fall back to Azure AD (RS256)
    try:
        claims = validate_email_jwt(token)
        logger.debug("Token validated as email JWT")
    except JWTError as e:
        logger.debug("Email JWT validation failed (%s), trying Azure AD", str(e))
        try:
            claims = validate_token(token)
            logger.debug("Token validated as Azure AD JWT")
        except Exception as exc:
            logger.warning("All token validations failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Entra ID surfaces group memberships as app roles when configured in the
    # app registration manifest under "appRoles". The claim name is "roles".
    roles: list[str] = claims.get("roles", [])

    # Fallback: every authenticated Entra user is at minimum a Requestor
    if not roles:
        roles = [Role.REQUESTOR]

    email = claims.get("preferred_username") or claims.get("upn") or claims.get("email", "")

    return UserClaims(
        oid=claims.get("oid"),  # May be None for email users
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


def generate_jwt_token(user) -> str:
    """Generate a JWT token for email-authenticated users.

    Tokens expire in 2 hours. Used only for email login, not Azure AD users.

    Args:
        user: User model instance from database

    Returns:
        JWT bearer token string
    """
    from datetime import datetime, timedelta, timezone
    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(hours=2)

    payload = {
        "sub": str(user.id),  # Use user.id instead of oid for email users
        "oid": user.oid,      # May be None for email-only users
        "email": user.email,
        "name": user.display_name,
        "roles": user.roles,
        "tid": "email-auth",  # Placeholder for email users
        "auth_source": user.auth_source,
        "exp": int(expiration.timestamp()),  # Convert to epoch timestamp
        "iat": int(now.timestamp()),         # Convert to epoch timestamp
    }

    # Use a fixed secret for email JWTs (in production, use a proper secret manager)
    secret_key = settings.AZURE_CLIENT_SECRET or "dev-email-jwt-secret-key"

    token = jwt.encode(payload, secret_key, algorithm="HS256")

    return token


def validate_email_jwt(token: str) -> dict:
    """Validate an email (HS256) JWT token."""
    secret = settings.AZURE_CLIENT_SECRET or "dev-email-jwt-secret-key"

    # Quick check: does it look like a JWT?
    if not token or token.count(".") != 2:
        logger.debug("Token is not a valid JWT format (expected 3 parts, got %d)", token.count(".") + 1)
        raise JWTError("Invalid JWT format")

    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
        return claims
    except JWTError as exc:
        logger.warning("Email JWT validation failed: %s", exc)
        raise JWTError(str(exc))
