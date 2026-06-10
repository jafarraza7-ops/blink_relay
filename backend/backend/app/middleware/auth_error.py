"""Middleware to convert auth-related 404 errors to 401 Unauthorized."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthErrorMiddleware(BaseHTTPMiddleware):
    """Convert 404 from failed auth dependencies to 401 Unauthorized.

    FastAPI returns 404 when a dependency fails to resolve. For auth-related
    dependencies, this leaks information about whether an endpoint exists.
    This middleware converts 404 responses to 401 when Authorization header is present.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # If auth was attempted (Authorization header present) and we got 404,
        # convert to 401 to avoid leaking endpoint existence
        has_auth_header = "authorization" in request.headers or "cookie" in request.headers

        if response.status_code == 404 and has_auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing authentication credentials"}
            )

        return response
