"""CSRF token generation and validation service."""
import secrets
import hashlib
import hmac
from typing import Optional
from datetime import datetime, timedelta


class CSRFTokenService:
    """Generate and validate CSRF tokens."""

    def __init__(self, secret_key: str):
        """Initialize with app secret key."""
        self.secret_key = secret_key.encode()

    def generate_token(self, session_id: str) -> str:
        """Generate a new CSRF token tied to a session.

        Args:
            session_id: User session ID or request ID

        Returns:
            CSRF token (base64-safe string)
        """
        # Generate random bytes and create signature
        random_bytes = secrets.token_hex(32)  # 64 hex chars
        timestamp = str(int(datetime.utcnow().timestamp()))

        # Create HMAC signature: HMAC(secret_key, random_bytes + timestamp)
        signature = hmac.new(
            self.secret_key,
            f"{random_bytes}{timestamp}{session_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        # Token format: random_bytes.timestamp.signature
        token = f"{random_bytes}.{timestamp}.{signature}"
        return token

    def validate_token(self, token: str, session_id: str, max_age_minutes: int = 30) -> bool:
        """Validate a CSRF token.

        Args:
            token: Token to validate
            session_id: User session ID or request ID
            max_age_minutes: Maximum age of token before expiry

        Returns:
            True if token is valid, False otherwise
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False

            random_bytes, timestamp_str, signature = parts

            # Verify signature
            expected_sig = hmac.new(
                self.secret_key,
                f"{random_bytes}{timestamp_str}{session_id}".encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                return False

            # Verify age
            token_time = datetime.fromtimestamp(int(timestamp_str))
            if datetime.utcnow() - token_time > timedelta(minutes=max_age_minutes):
                return False

            return True

        except (ValueError, IndexError, TypeError):
            return False
