"""CSRF protection middleware."""
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.services.csrf_service import CSRFTokenService
from app.core.config import get_settings


class CSRFMiddleware(BaseHTTPMiddleware):
    """Add CSRF token to responses and validate on state-changing requests.

    CSRF tokens are generated for each response and must be included in:
    - POST requests
    - PUT requests
    - DELETE requests
    - PATCH requests

    Exempt endpoints (typically public or auth-related):
    - POST /api/auth/* (auth endpoints use different validation)
    - POST /api/webhook/* (webhooks have signature validation)
    """

    # Endpoints exempt from CSRF validation
    EXEMPT_PATHS = {
        "/api/auth/",
        "/api/webhook/",
        "/health",
        "/docs",
        "/redoc",
    }

    # Methods that require CSRF token
    CSRF_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    def __init__(self, app, secret_key: Optional[str] = None):
        super().__init__(app)
        settings = get_settings()
        self.secret_key = secret_key or settings.AZURE_CLIENT_SECRET or "dev-secret-key"
        self.csrf_service = CSRFTokenService(self.secret_key)

    def _should_verify_csrf(self, request: Request) -> bool:
        """Check if this request requires CSRF validation."""
        if request.method not in self.CSRF_METHODS:
            return False

        # Check if path is exempt
        for exempt_path in self.EXEMPT_PATHS:
            if request.url.path.startswith(exempt_path):
                return False

        return True

    def _get_session_id(self, request: Request) -> str:
        """Get session ID from request (auth header, cookie, or default)."""
        # Try to extract from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header:
            return auth_header[:50]  # First 50 chars of token as session ID

        # Try to extract from cookies
        cookie_header = request.headers.get("Cookie", "")
        if cookie_header:
            return cookie_header[:50]

        # Fallback to remote address
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        # Generate session ID
        session_id = self._get_session_id(request)

        # Get response first
        response = await call_next(request)

        # Add CSRF token to response headers for client to use
        token = self.csrf_service.generate_token(session_id)
        response.headers["X-CSRF-Token"] = token

        # Validate CSRF on state-changing requests
        if self._should_verify_csrf(request):
            csrf_token = request.headers.get("X-CSRF-Token")

            if not csrf_token:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing"}
                )

            if not self.csrf_service.validate_token(csrf_token, session_id):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid CSRF token"}
                )

        return response
