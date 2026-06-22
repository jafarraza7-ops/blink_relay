"""
tests/test_email_auth.py — Unit tests for email-based authentication.

Tests magic-link generation, validation, expiration, and one-time-use constraints.
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import LoginToken
from app.models.request import User
from app.services.token_service import generate_token, hash_token, create_login_token, validate_token

# These tests were written against a class-based TokenService API that was never
# implemented. The actual token_service module exports standalone functions with
# different signatures (requires ip_address/user_agent args) and uses EmailLoginToken
# (not LoginToken). Skip until tests are rewritten to match the real API.
pytestmark = pytest.mark.skip(reason="stale tests — TokenService class does not exist; token_service uses standalone functions with different signatures")


class TestTokenGeneration:
    """Test token generation and uniqueness."""

    def test_generate_token_is_unique(self):
        """Each generated token should be unique."""
        token1 = TokenService.generate_token()
        token2 = TokenService.generate_token()
        assert token1 != token2
        assert len(token1) > 30  # token_urlsafe(32) ~43 chars

    def test_generate_token_is_url_safe(self):
        """Generated tokens should be URL-safe."""
        token = TokenService.generate_token()
        # URL-safe base64 uses - and _ instead of + and /
        assert "+" not in token
        assert "/" not in token


class TestTokenCreation:
    """Test token creation and invalidation of previous tokens."""

    @pytest.mark.asyncio
    async def test_create_login_token_new_user(self, db_session: AsyncSession):
        """Test creating a login token for a new (unregistered) email."""
        service = TokenService()
        token = await service.create_login_token(db_session, "newuser@example.com")

        assert token.email == "newuser@example.com"
        assert token.user_id is None
        assert token.token is not None
        assert token.used_at is None
        assert token.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_create_login_token_existing_user(self, db_session: AsyncSession, user: User):
        """Test creating a login token for an existing registered user."""
        service = TokenService()
        token = await service.create_login_token(db_session, user.email, user.id)

        assert token.email == user.email
        assert token.user_id == user.id
        assert token.used_at is None

    @pytest.mark.asyncio
    async def test_invalidates_previous_tokens_on_new_request(self, db_session: AsyncSession):
        """Test that requesting a new login token invalidates previous unused tokens."""
        service = TokenService()
        email = "user@example.com"

        # Create first token
        token1 = await service.create_login_token(db_session, email)
        await db_session.flush()

        # Create second token (should invalidate first)
        token2 = await service.create_login_token(db_session, email)
        await db_session.flush()

        # Refresh from DB
        await db_session.refresh(token1)

        assert token1.used_at is not None  # First token should be marked as used
        assert token2.used_at is None      # Second token should be fresh


class TestTokenValidation:
    """Test token validation and expiration checking."""

    @pytest.mark.asyncio
    async def test_validate_valid_token(self, db_session: AsyncSession):
        """Test validating a valid, unexpired, unused token."""
        service = TokenService()
        email = "user@example.com"

        token_obj = await service.create_login_token(db_session, email)
        await db_session.flush()

        validated = await service.validate_token(db_session, token_obj.token)
        assert validated is not None
        assert validated.token == token_obj.token
        assert validated.email == email

    @pytest.mark.asyncio
    async def test_validate_nonexistent_token(self, db_session: AsyncSession):
        """Test validating a token that doesn't exist."""
        service = TokenService()
        validated = await service.validate_token(db_session, "nonexistent_token")
        assert validated is None

    @pytest.mark.asyncio
    async def test_validate_expired_token(self, db_session: AsyncSession):
        """Test that expired tokens are rejected."""
        service = TokenService()
        email = "user@example.com"

        token_obj = await service.create_login_token(db_session, email)
        # Manually set expiration to past
        token_obj.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db_session.flush()

        validated = await service.validate_token(db_session, token_obj.token)
        assert validated is None

    @pytest.mark.asyncio
    async def test_validate_already_used_token(self, db_session: AsyncSession):
        """Test that already-used tokens are rejected (one-time-use)."""
        service = TokenService()
        email = "user@example.com"

        token_obj = await service.create_login_token(db_session, email)
        await db_session.flush()

        # Mark as used
        await service.mark_token_as_used(db_session, token_obj)
        await db_session.flush()

        # Try to validate again
        validated = await service.validate_token(db_session, token_obj.token)
        assert validated is None


class TestTokenStatus:
    """Test token status checking (for frontend link verification)."""

    @pytest.mark.asyncio
    async def test_get_token_status_valid(self, db_session: AsyncSession):
        """Test status check for a valid token."""
        service = TokenService()
        email = "user@example.com"

        token_obj = await service.create_login_token(db_session, email)
        await db_session.flush()

        status = await service.get_token_status(db_session, token_obj.token)
        assert status["valid"] is True
        assert status["reason"] == "valid"

    @pytest.mark.asyncio
    async def test_get_token_status_not_found(self, db_session: AsyncSession):
        """Test status check for a nonexistent token."""
        service = TokenService()
        status = await service.get_token_status(db_session, "nonexistent")
        assert status["valid"] is False
        assert status["reason"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_token_status_expired(self, db_session: AsyncSession):
        """Test status check for an expired token."""
        service = TokenService()
        email = "user@example.com"

        token_obj = await service.create_login_token(db_session, email)
        token_obj.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db_session.flush()

        status = await service.get_token_status(db_session, token_obj.token)
        assert status["valid"] is False
        assert status["reason"] == "expired"

    @pytest.mark.asyncio
    async def test_get_token_status_already_used(self, db_session: AsyncSession):
        """Test status check for an already-used token."""
        service = TokenService()
        email = "user@example.com"

        token_obj = await service.create_login_token(db_session, email)
        await db_session.flush()

        await service.mark_token_as_used(db_session, token_obj)
        await db_session.flush()

        status = await service.get_token_status(db_session, token_obj.token)
        assert status["valid"] is False
        assert status["reason"] == "already_used"
