# Email Login System Implementation Guide

## Overview

This document describes the email-based passwordless authentication system for Blink Relay, enabling users to sign in via magic links sent to their email.

## Architecture

### Flow Diagram

```
User visits login page
         ↓
User enters email → POST /auth/login
         ↓
Backend generates LoginToken (15 min expiry)
         ↓
Send email with magic link + token
         ↓
User clicks link → Frontend calls GET /auth/login-status/:token (optional)
         ↓
Frontend shows "Signing in..." → POST /auth/verify with token
         ↓
Backend validates token, creates/updates user
         ↓
Backend returns JWT access_token
         ↓
Frontend stores token, authenticated user can access app
```

## Database Schema

### LoginToken Table

```sql
CREATE TABLE login_tokens (
    id UUID PRIMARY KEY,
    token VARCHAR(256) UNIQUE NOT NULL,
    email VARCHAR(254) NOT NULL,
    user_id UUID NULLABLE REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE NULLABLE
);

CREATE INDEX ix_login_tokens_token ON login_tokens(token);
CREATE INDEX ix_login_tokens_email ON login_tokens(email);
```

### User Table Changes

- Made `oid` nullable to support email-auth users (initially without Entra ID mapping)
- Added `email_verified` flag to track email verification status for passwordless users

```sql
ALTER TABLE users 
  MODIFY COLUMN oid VARCHAR(36) NULLABLE;

ALTER TABLE users 
  ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE;
```

## API Endpoints

### 1. POST /auth/login
**Initiate email login** — Generate and send magic link token.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (202 Accepted):**
```json
{
  "message": "If an account exists for this email, a login link has been sent"
}
```

**Key behaviors:**
- Always returns 202 success (prevents email enumeration attacks)
- Invalidates any previous unused tokens for the email (1 active token per email)
- Email is case-insensitive (lowercased before storage)
- Non-blocking email delivery (failures logged, don't fail request)
- Token expires in 15 minutes (configurable via `TokenService.TOKEN_EXPIRATION_MINUTES`)

### 2. POST /auth/verify
**Complete email login** — Verify token and create/update user.

**Request:**
```json
{
  "token": "4Qyw3...abcdef123456",
  "display_name": "John Doe"  // Optional; required only for new signups
}
```

**Response (200 OK):**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "display_name": "John Doe",
  "access_token": "eyJ0eXA...",
  "token_type": "bearer"
}
```

**Status codes:**
- `200` — Token valid, user created/updated, JWT returned
- `400` — Token invalid, expired, or already used
- `422` — New signup but `display_name` missing

**Key behaviors:**
- Creates new user if email doesn't exist (signup flow)
- Updates existing user if already registered
- Marks email as verified on first successful login
- Marks token as "used" to prevent reuse
- Returns JWT access token (placeholder implementation; see [JWT Implementation](#jwt-implementation) below)

### 3. GET /auth/login-status/{token}
**Check token validity** — For frontend link verification before calling `/verify`.

**Response (200 OK):**
```json
{
  "valid": true,
  "reason": "valid",
  "email": "user@example.com"
}
```

**Possible reasons:**
- `"valid"` — Token is valid and can be used
- `"not_found"` — Token doesn't exist
- `"expired"` — Token has expired
- `"already_used"` — Token has already been redeemed

**Key behaviors:**
- Does NOT consume the token (can still verify afterward)
- Returns email only if token is valid (useful for "Sign in as: ..." UI)
- Used by frontend for progressive link validation

## Services

### TokenService

**Location:** `app/services/token_service.py`

**Responsibilities:**
- Generate cryptographically strong tokens
- Create and validate login tokens
- Enforce expiration and one-time-use constraints
- Check token status for frontend

**Key methods:**

```python
@staticmethod
def generate_token() -> str
    """Generate a URL-safe 256-bit random token (~43 chars)."""

async def create_login_token(db, email, user_id=None) -> LoginToken
    """Create token; invalidates previous unused tokens for email."""

async def validate_login_token(db, token) -> LoginToken | None
    """Check expiration and one-time-use constraints."""

async def mark_token_as_used(db, login_token) -> None
    """Mark token as used (prevent reuse)."""

async def get_token_status(db, token) -> dict
    """Get token status without consuming it."""
```

**Configuration:**
- `TOKEN_EXPIRATION_MINUTES = 15` — Token lifetime (in minutes)

### EmailService

**Location:** `app/services/email_service.py`

**Extends:** `NotificationService` (adds email-auth-specific templates)

**Key methods:**

```python
async def send_magic_link(
    self,
    email: str,
    login_link: str,
    token_expires_in_minutes: int = 15,
) -> None
    """Send magic-link email with security warnings."""
```

**Email template:**
- Professional HTML layout using existing `_html_wrap()` helper
- CTA button with login link
- Token expiration time displayed
- Security warnings (don't share link, no password, report abuse)
- Uses configured email backend (SMTP for dev, Graph API for prod)

## Security Considerations

### Token Security

1. **Cryptographically Strong Generation**
   - Uses `secrets.token_urlsafe(32)` (256-bit, URL-safe base64)
   - Python `secrets` module is guaranteed cryptographically secure

2. **One-Time-Use Enforcement**
   - Token marked as "used" immediately after successful verification
   - Attempting to reuse expired or used token returns 400 error
   - Previous unused tokens invalidated when new login is requested (prevents token stockpiling)

3. **Time-Limited Tokens**
   - 15-minute expiration (configurable)
   - Frontend checks token status to handle expired links gracefully
   - Expired tokens rejected with clear error message

4. **Plaintext Storage Warning**
   - Current implementation stores tokens in plaintext
   - **For production:** Hash tokens using `argon2` or similar
     ```python
     from argon2 import PasswordHasher
     ph = PasswordHasher()
     hashed_token = ph.hash(token)
     # Store hashed_token in DB, compare on verification
     ```

### Email Safety

1. **Email Enumeration Prevention**
   - POST /auth/login always returns 202 success, even for non-existent emails
   - Attacker cannot determine which emails are registered
   - Rate limiting recommended at application gateway level

2. **Email Delivery Safety**
   - Email failures don't block login flow (failures logged for monitoring)
   - Ensures better UX when SMTP is misconfigured

3. **XSS Prevention**
   - Email HTML is generated server-side (no user input in templates)
   - Login link URL-encoded before inclusion in HTML

### Authorization

1. **New vs. Existing Users**
   - Existing Entra ID users: Email must match registered email, uses existing OID
   - Email-auth users: Can sign up with display_name, no Entra ID mapping initially
   - Entra sync can later link email-auth accounts to Entra IDs (set oid field)

2. **Role Assignment**
   - New email-auth users default to "Requestor" role (read-only)
   - Can be promoted to ProductManager/Admin via admin interface

3. **Email Verification**
   - Email-auth users marked `email_verified=true` immediately after token validation
   - Entra ID users inherit their organization role mappings

## Implementation Checklist

### Database Migrations

- [x] Create migration `009_email_auth_system.py`
- [x] Add `email_verified` column to users table
- [x] Make `oid` nullable in users table
- [x] Create `login_tokens` table with indexes

### Models

- [x] Create `LoginToken` model in `app/models/auth.py`
- [x] Update `User` model (nullable oid, email_verified flag)
- [x] Export LoginToken from `app/models/__init__.py`

### Services

- [x] Create `TokenService` (token generation, validation, status)
- [x] Create `EmailService` (magic-link email template)

### API Endpoints

- [x] Create `email_auth.py` router with 3 endpoints
  - [x] POST /auth/login
  - [x] POST /auth/verify
  - [x] GET /auth/login-status/:token
- [x] Register router in `main.py`

### Testing

- [x] Create `test_email_auth.py` with comprehensive tests
  - Token generation uniqueness
  - Token creation and previous token invalidation
  - Token validation (valid, expired, already-used)
  - Token status checking

### Frontend Integration

- [ ] Create login page with email input
- [ ] Implement email verification link handler
- [ ] Call GET /auth/login-status/:token for link validation
- [ ] Call POST /auth/verify with token and (optionally) display_name
- [ ] Store JWT token in localStorage/sessionStorage
- [ ] Include token in Authorization header for subsequent requests

### Production Considerations

- [ ] Implement proper JWT signing (python-jose or PyJWT)
- [ ] Hash tokens before storage (argon2)
- [ ] Add rate limiting (e.g., max 5 login attempts per email per hour)
- [ ] Add CAPTCHA for signup/login endpoints
- [ ] Set up email delivery monitoring (bounce/complaint handling)
- [ ] Consider magic link length (currently ~100 chars with token)
- [ ] Add audit logging for successful/failed login attempts
- [ ] Configure FRONTEND_URL environment variable
- [ ] Set up monitoring alerts for token expiration/usage patterns

## JWT Implementation

**Current status:** Placeholder implementation in `_generate_jwt_token()`

**Production implementation** should:

```python
from jose import jwt
from datetime import timedelta

def _generate_jwt_token(user_id: uuid.UUID, email: str, display_name: str) -> str:
    claims = {
        "sub": str(user_id),
        "email": email,
        "name": display_name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "jti": str(uuid.uuid4()),  # Unique token ID for revocation
    }
    token = jwt.encode(
        claims,
        settings.SECRET_KEY,  # Add to config
        algorithm="HS256"  # or RS256 with public/private key
    )
    return token
```

**Required additions to `app/core/config.py`:**

```python
JWT_SECRET_KEY: str = ""  # Load from Key Vault in prod
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRATION_HOURS: int = 24
```

## Environment Configuration

Add to `.env`:

```bash
# Email authentication (already configured)
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.ethereal.email
SMTP_PORT=587
SMTP_USER=<ethereal-email>
SMTP_PASS=<ethereal-password>
SMTP_FROM=<sender-address>

# Frontend URL for magic links
FRONTEND_URL=http://localhost:5173

# JWT signing (when implementing)
# JWT_SECRET_KEY=<random-secret>
```

## Monitoring and Observability

**Recommended metrics/logs:**

- Login attempts by email (prevent enumeration)
- Token generation rate (detect abuse)
- Token expiration reasons (valid, expired, not found, already used)
- Email delivery failures (integration health)
- Successful logins (audit trail)

**Example log patterns:**

```
INFO: Login token sent to email=user@example.com, expires_in=15 min
INFO: User authenticated via email: id=550e8400..., email=user@example.com
INFO: Created new user via email signup: email=user@example.com, id=550e8400...
WARNING: Login token not found: 4Qyw3...
WARNING: Login token expired: 4Qyw3...
WARNING: Login token already used: 4Qyw3...
```

## Testing Locally

### Without email delivery:

1. Set `EMAIL_BACKEND=smtp` and valid Ethereal credentials in `.env`
2. Or set `CELERY_TASK_ALWAYS_EAGER=true` and catch email in logs

### Using Ethereal Email:

1. Create free account at https://ethereal.email
2. Set `SMTP_USER` and `SMTP_PASS` in `.env`
3. Check inbox at https://ethereal.email/messages after login attempt

### Manual testing:

```bash
# Start backend
cd backend && python -m uvicorn main:app --reload

# Request login link
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Check token status (get token from logs or Ethereal)
curl http://localhost:8000/api/auth/login-status/4Qyw3...

# Verify token
curl -X POST http://localhost:8000/api/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "4Qyw3...", "display_name": "Test User"}'
```

## API Error Codes

| Endpoint | Status | Reason |
|----------|--------|--------|
| POST /auth/login | 202 | Always success (email enumeration prevention) |
| POST /auth/login | 400 | Invalid email format |
| POST /auth/verify | 200 | Token valid, JWT returned |
| POST /auth/verify | 400 | Token invalid/expired/already-used |
| POST /auth/verify | 422 | New signup missing display_name |
| GET /auth/login-status/:token | 200 | Status retrieved (token may be invalid) |

## Files Modified/Created

**Created:**
- `app/models/auth.py` — LoginToken ORM model
- `app/services/email_service.py` — Magic-link email template
- `app/services/token_service.py` — Token generation/validation logic
- `app/api/email_auth.py` — API endpoints (login, verify, status)
- `alembic/versions/009_email_auth_system.py` — Database migration
- `tests/test_email_auth.py` — Comprehensive unit tests

**Modified:**
- `app/models/request.py` — User model (nullable oid, email_verified flag)
- `app/models/__init__.py` — Export LoginToken
- `main.py` — Register email_auth router

## Future Enhancements

1. **Token hashing** — Store only hashed tokens to prevent DB breach exposure
2. **Rate limiting** — Limit login attempts per email per hour
3. **CAPTCHA** — Add human verification on signup/login
4. **Social login** — Add Google/GitHub OAuth as alternative to email
5. **Account linking** — Link email-auth users to Entra ID when they authenticate via MS
6. **Session management** — Implement JWT refresh tokens and token revocation
7. **Multi-factor auth** — Add TOTP or SMS MFA for security
8. **Account recovery** — Password reset flow for future password-based auth
