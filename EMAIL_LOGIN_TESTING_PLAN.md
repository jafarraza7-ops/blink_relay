# Email Login Workflow Testing Plan

## Overview

This document outlines comprehensive manual and automated test cases for the email-based passwordless authentication workflow in Blink Relay. The workflow consists of three main endpoints:

1. **POST /api/auth/login** — Initiate login (send magic link via email)
2. **GET /api/auth/login-status/{token}** — Check token validity (no consumption)
3. **POST /api/auth/verify** — Complete login (consume token, create/return JWT)

### Key Constraints
- **Token Expiration**: 15 minutes
- **Token Usage**: Single-use only (one-time use constraint)
- **User Creation**: Automatic on first signup with email
- **Email Enumeration Protection**: Always returns 202 success, even if email not found

---

## 1. Happy Path Testing

### Test Case 1.1: New User Email Signup (Happy Path)
**Objective**: Verify complete email signup flow for a new user

**Steps**:
1. Navigate to `/login`
2. Enter a new email address (not in system): `newuser_test_001@blinkcharging.com`
3. Click "Send Login Link"
4. **Verify**: Page shows "Check your email" confirmation
5. Open email client and locate the email from Blink Relay
6. Click the "Verify your email & sign in" button in email
7. **Verify**: Redirected to `/auth/email-verify?token=<token>`
8. **Verify**: Page shows "Verifying your login link…" briefly
9. **Verify**: Presented with login form asking for display_name
10. Enter display name: `Test User`
11. Click "Complete signup"
12. **Verify**: Page shows "Login successful!" with checkmark
13. **Verify**: Redirected to `/my-requests` within 2 seconds
14. **Verify**: Can see personal request list (user is logged in)
15. **Verify**: localStorage contains `accessToken` and `currentUser` with correct user ID, email, and display_name

**Expected Results**:
- Account is created in `users` table with email verified
- JWT token is valid and can make authenticated API calls
- User role defaults to "Requestor"

---

### Test Case 1.2: Existing User Email Login
**Objective**: Verify login flow for an already-registered user

**Prerequisites**: User already exists in system (e.g., synced from Entra ID or previously email-authed)

**Steps**:
1. Navigate to `/login`
2. Enter existing user email: `existing_user@blinkcharging.com`
3. Click "Send Login Link"
4. **Verify**: Page shows "Check your email" confirmation
5. Open email and click login link
6. **Verify**: Redirected to token verification page
7. **Verify**: Page shows "Verifying your login link…"
8. **Verify**: No display_name form shown (user already exists)
9. **Verify**: Page shows "Login successful!" and redirects to `/my-requests`
10. **Verify**: Can access authenticated endpoints immediately
11. **Verify**: User's email is marked as verified in database

**Expected Results**:
- Existing user account is updated (email_verified = true if not already)
- JWT token returned without requiring display_name
- Seamless login experience

---

### Test Case 1.3: Smooth Loading States
**Objective**: Verify UI loading states feel responsive and provide clear feedback

**Steps**:
1. On EmailLoginPage, enter valid email and click "Send Login Link"
2. **Verify**: Button shows spinner and "Sending link…" text
3. **Verify**: Email input is disabled during request
4. **Verify**: After response (2-3 sec), success message appears
5. Open email and click link
6. **Verify**: VerifyTokenPage shows "Verifying your login link…" with spinner
7. **Verify**: Spinner persists for ~1 second
8. **Verify**: Upon success, displays "Login successful!" with spinner
9. **Verify**: No jarring transitions between states
10. Transition from page to page should be smooth without flickering

**Expected Results**:
- All loading states use consistent spinner style
- Buttons disable during requests
- Text updates clearly indicate current operation
- Timing feels natural (~1-2s for verification)

---

## 2. Edge Case Testing

### Test Case 2.1: Expired Token (Older than 15 Minutes)
**Objective**: Verify expired tokens are rejected and user gets clear feedback

**Prerequisites**: Token created and ready to test

**Steps**:
1. Send login request for `expire_test@blinkcharging.com`
2. Retrieve the token from database (or email)
3. Manually set `expires_at` to 16 minutes ago: `datetime.now(UTC) - timedelta(minutes=16)`
4. Copy the token and attempt to access: `/auth/email-verify?token=<expired_token>`
5. **Verify**: Page loads and shows "Verifying your login link…"
6. **Verify**: After status check, displays Clock icon and "Login link expired"
7. **Verify**: Error message: "Login links are valid for 15 minutes. Please request a new one."
8. **Verify**: "Request new login link" button is visible and functional
9. Click button and get a fresh token
10. **Verify**: Fresh token works correctly

**Expected Results**:
- GET /api/auth/login-status/{expired_token} returns `{valid: false, reason: "expired"}`
- POST /api/auth/verify rejects expired token with 400 Bad Request
- User can request a new link without friction

**Automated Test**:
```python
@pytest.mark.asyncio
async def test_expired_token_rejected(db_session, email_service):
    service = TokenService()
    token = await service.create_login_token(db_session, "expire@test.com")
    token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()
    
    status = await service.get_token_status(db_session, token.token)
    assert status["reason"] == "expired"
    assert status["valid"] is False
    
    with pytest.raises(HTTPException) as exc:
        result = await verify(VerifyRequest(token=token.token), db_session)
    assert exc.value.status_code == 400
```

---

### Test Case 2.2: Already-Used Token (Clicking Link Twice)
**Objective**: Verify one-time-use constraint prevents token reuse

**Steps**:
1. Send login request for `reuse_test@blinkcharging.com`
2. Open email and copy the token from the URL
3. Click the email link and complete login (or open in first browser tab)
4. **Verify**: Redirected to `/my-requests` and logged in
5. Open a new browser tab/incognito and paste the same token URL: `/auth/email-verify?token=<used_token>`
6. **Verify**: Page shows "Verifying your login link…"
7. **Verify**: After status check, displays AlertCircle icon and "Link already used"
8. **Verify**: Error message: "This login link was already used. If that wasn't you, request a new login link."
9. **Verify**: "Request new login link" button is present
10. Click button and verify new flow works

**Expected Results**:
- Token's `used_at` field is set after successful verification
- GET /api/auth/login-status/{used_token} returns `{valid: false, reason: "already_used"}`
- POST /api/auth/verify rejects already-used token with 400 Bad Request
- Security maintained (someone cannot use a leaked link multiple times)

**Automated Test**:
```python
@pytest.mark.asyncio
async def test_token_one_time_use(db_session, user):
    service = TokenService()
    token = await service.create_login_token(db_session, user.email, user.id)
    await db_session.flush()
    
    # First verification succeeds
    result = await verify(VerifyRequest(token=token.token), db_session)
    assert result.user_id == str(user.id)
    
    # Second verification fails
    with pytest.raises(HTTPException):
        await verify(VerifyRequest(token=token.token), db_session)
```

---

### Test Case 2.3: Invalid/Malformed Token
**Objective**: Verify malformed tokens are rejected

**Steps**:
1. Try to access `/auth/email-verify?token=invalid_token_xyz`
2. **Verify**: Page shows "Verifying your login link…"
3. **Verify**: After status check, displays AlertCircle icon
4. **Verify**: Error message: "This login link is invalid or not found."
5. Click "Try again" and request new link
6. Try with empty token: `/auth/email-verify?token=`
7. **Verify**: Error message shown
8. Try with malicious token: `/auth/email-verify?token='; DROP TABLE--`
9. **Verify**: Token treated as literal string, safely rejected
10. Try with token containing special characters: `/auth/email-verify?token=abc%20def%2Bghi`
11. **Verify**: URL-decoded properly and rejected as invalid

**Expected Results**:
- GET /api/auth/login-status/{invalid_token} returns `{valid: false, reason: "not_found"}`
- POST /api/auth/verify with invalid token returns 400 Bad Request
- No SQL injection or token parsing vulnerabilities

**Automated Test**:
```python
@pytest.mark.asyncio
async def test_invalid_token_rejected(db_session):
    service = TokenService()
    
    invalid_tokens = [
        "nonexistent_token",
        "'; DROP TABLE login_tokens--",
        "",
        "a" * 500,
        "../../etc/passwd"
    ]
    
    for invalid_token in invalid_tokens:
        status = await service.get_token_status(db_session, invalid_token)
        assert status["valid"] is False
        assert status["reason"] == "not_found"
```

---

### Test Case 2.4: Email Not Found (Email Enumeration Protection)
**Objective**: Verify email enumeration attack is prevented

**Steps**:
1. Request login for email that definitely doesn't exist: `nonexistent_9999@example.com`
2. **Verify**: Still returns 202 Accepted: "If an account exists for this email, a login link has been sent"
3. **Verify**: No email is sent (attacker cannot tell via email received/not received)
4. Request login for email that DOES exist: `existing@blinkcharging.com`
5. **Verify**: Also returns 202 Accepted with same message
6. **Verify**: Email IS sent to existing user
7. Attacker has no way to distinguish between existing and non-existing accounts

**Expected Results**:
- POST /api/auth/login always returns 202 (regardless of email existence)
- Email is only sent for emails that exist in system OR would be new signups
- Response message is identical for both cases
- No timing differences that could leak information

**Automated Test**:
```python
@pytest.mark.asyncio
async def test_email_enumeration_protection(db_session):
    """Verify identical response for existing and non-existing emails."""
    existing_email = "existing@test.com"
    nonexistent_email = "definitely_not_real_999@test.com"
    
    # Create existing user
    user = User(email=existing_email)
    db_session.add(user)
    await db_session.flush()
    
    # Both requests should return identical status code
    response_existing = await login(LoginRequest(email=existing_email), db_session)
    response_nonexistent = await login(LoginRequest(email=nonexistent_email), db_session)
    
    assert response_existing.status_code == 202
    assert response_nonexistent.status_code == 202
    # Response body should be identical
    assert response_existing.body == response_nonexistent.body
```

---

### Test Case 2.5: Multiple Login Requests from Same Email
**Objective**: Verify that requesting multiple login links invalidates previous ones (only 1 active token per email)

**Steps**:
1. Request login for `multi_request@blinkcharging.com`
2. Receive first email with token_1
3. Copy token_1 and note it
4. Request login AGAIN for same email (user didn't receive first email or wants a fresh link)
5. Receive second email with token_2 (different from token_1)
6. **Verify**: `token_1` is now invalid (check via `/api/auth/login-status/token_1`)
7. **Verify**: Status returns `{valid: false, reason: "expired"...}` or similar
8. **Verify**: `token_2` is valid
9. Verify using token_2 works correctly
10. Attempt to use token_1 (should fail)
11. **Verify**: `/api/auth/verify` with token_1 returns 400 Bad Request

**Expected Results**:
- Only 1 active (unused) token exists per email at a time
- Creating a new token marks all previous unused tokens as used
- Previous token becomes unusable immediately
- User always has the latest link in their inbox

**Automated Test**:
```python
@pytest.mark.asyncio
async def test_only_one_active_token_per_email(db_session):
    """Verify that creating a new token invalidates previous ones."""
    service = TokenService()
    email = "multitoken@test.com"
    
    # Create first token
    token1 = await service.create_login_token(db_session, email)
    await db_session.flush()
    
    # Create second token
    token2 = await service.create_login_token(db_session, email)
    await db_session.flush()
    
    # Refresh token1 from DB
    await db_session.refresh(token1)
    
    # First token should be marked as used
    assert token1.used_at is not None
    
    # Second token should be unused
    assert token2.used_at is None
    
    # First token should fail validation
    validated = await service.validate_login_token(db_session, token1.token)
    assert validated is None
    
    # Second token should pass validation
    validated = await service.validate_login_token(db_session, token2.token)
    assert validated is not None
```

---

## 3. Integration Testing

### Test Case 3.1: Email Login → View MY REQUESTS
**Objective**: Verify authenticated user can immediately access their request list after login

**Steps**:
1. Complete email login flow (Test Case 1.1 or 1.2)
2. **Verify**: Redirected to `/my-requests`
3. **Verify**: Page loads and shows authenticated content
4. **Verify**: Can see request list filtered to user's own requests
5. **Verify**: Filter pills/dropdowns are functional
6. **Verify**: Can apply filters (status, region, etc.)
7. **Verify**: Can access CSV export (if PM/reviewer role)
8. **Verify**: Pagination works if applicable
9. Log out and log back in with different email
10. **Verify**: Different user sees only their own requests
11. **Verify**: No cross-contamination of request data

**Expected Results**:
- JWT token is valid for authenticated API calls
- User role/permissions enforced at API level
- Request list is filtered to current user
- All downstream features work with email-authed users

---

### Test Case 3.2: Email Login → View Conversation Threads
**Objective**: Verify authenticated users can read request details and conversation threads

**Steps**:
1. Complete email login flow
2. Navigate to MY REQUESTS page
3. Click on a request created by this user
4. **Verify**: Request details page loads (e.g., `/request/:id`)
5. **Verify**: Can see all conversation threads
6. **Verify**: Can see who created each comment (display names, initials)
7. **Verify**: Can see timestamps and thread nesting
8. **Verify**: Can read all comments without errors
9. Scroll through long threads to verify pagination/loading
10. **Verify**: No 401/403 errors when accessing threads

**Expected Results**:
- Email-authed users have permission to view request details
- Comment threads load correctly
- No missing comments or data integrity issues

---

### Test Case 3.3: Email Login → Add Comments with @ Mentions
**Objective**: Verify authenticated users can add comments and mention other users

**Prerequisites**: Request already exists and user is logged in

**Steps**:
1. Complete email login flow
2. Navigate to a request detail page
3. Scroll to comment box
4. Type a comment: `@Test User, please review this request.`
5. **Verify**: @ mentions trigger user search/autocomplete
6. **Verify**: Can select user from dropdown
7. **Verify**: Selected user is highlighted or tagged
8. Click "Submit Comment"
9. **Verify**: Comment is added to thread
10. **Verify**: Mentioned user receives notification (if notifications enabled)
11. **Verify**: Display name is shown in comment (not hidden for email-authed users)
12. Mention another user and verify mention formatting is correct
13. Check database that mention is stored correctly

**Expected Results**:
- Comments can be posted by email-authed users
- @ mention system works correctly
- Notifications are triggered for mentioned users
- No permission issues when posting comments

---

### Test Case 3.4: Logout Flow
**Objective**: Verify clean logout and session termination

**Steps**:
1. Complete email login flow
2. Navigate to an authenticated page (e.g., `/my-requests`)
3. Click logout button (typically in header/nav)
4. **Verify**: localStorage is cleared (accessToken and currentUser removed)
5. **Verify**: Redirected to `/login` or home page
6. **Verify**: Navigation bar shows "Sign in" instead of user name
7. Try to navigate directly to `/my-requests` (authenticated route)
8. **Verify**: Redirected to login page automatically (route guard working)
9. Attempt API call with old JWT (if cached)
10. **Verify**: Request fails with 401 Unauthorized
11. Verify entire session is terminated

**Expected Results**:
- All auth data is cleared from browser
- User cannot access protected pages
- Cannot make authenticated API calls with old token
- Clean state for next login

---

## 4. Security Testing

### Test Case 4.1: Token Format & Information Leakage
**Objective**: Verify tokens don't expose sensitive information and are URL-safe

**Steps**:
1. Obtain a valid login token via `/api/auth/login`
2. Examine token format:
   - Token should be URL-safe (no special chars requiring encoding)
   - Token should be ~43 characters (base64-encoded 32-byte random value)
   - Token should NOT contain user_id, email, or other info in plaintext
3. If token is JWT format (contains `.` separators):
   - Decode payload (JWT.io or atob())
   - **Verify**: Payload does NOT contain email, user_id, or other sensitive data
   - **Verify**: Payload contains only `sub`, `email`, `name` (from frontend code)
4. Check database:
   - Token is stored as plaintext in `login_tokens.token` column (acceptable for single-use tokens)
   - Could be hashed in production (not critical for 15-min expiry tokens)
5. Test token across different mediums:
   - Paste in email client without URL encoding (should work)
   - Share in Slack/Teams (should work)
   - Pass as query parameter in URL (should work)

**Expected Results**:
- Tokens are URL-safe and don't require encoding
- Tokens don't leak sensitive information
- Tokens appear random and cannot be guessed
- Token format is consistent across all generations

**Automated Test**:
```python
def test_token_format_and_randomness():
    """Verify tokens are URL-safe and random."""
    service = TokenService()
    tokens = [service.generate_token() for _ in range(100)]
    
    # All unique
    assert len(set(tokens)) == 100
    
    # All URL-safe (no + / = in base64)
    for token in tokens:
        assert '+' not in token
        assert '/' not in token
        assert token.endswith('=') is False
    
    # All similar length (43 chars for token_urlsafe(32))
    lengths = [len(t) for t in tokens]
    assert min(lengths) >= 40 and max(lengths) <= 45
```

---

### Test Case 4.2: CSRF Protection (Cross-Site Request Forgery)
**Objective**: Verify CSRF attacks cannot bypass authentication

**Steps** (requires attack simulation or CSRF testing tool):
1. Examine frontend code for CSRF tokens or SameSite cookie attributes
2. Check if `/api/auth/verify` requires:
   - SameSite=Strict or SameSite=Lax on any cookies
   - CSRF token in request headers
   - Origin/Referer header validation
3. Attempt POST to `/api/auth/verify` from a different origin:
   - Create HTML form on attacker.com that POSTs to `/api/auth/verify`
   - **Verify**: Request fails due to CORS or CSRF protection
4. Check if login endpoint has rate limiting (Test Case 4.3 handles this)
5. Verify JWT tokens are not stored in cookies (stored in localStorage instead, safer)

**Expected Results**:
- CORS middleware blocks cross-origin requests (configured in main.py)
- No CSRF token required (acceptable since using email-based auth, not cookies)
- SameSite policy on any cookies prevents CSRF
- Tokens are in localStorage (HttpOnly is not needed for this design)

---

### Test Case 4.3: Rate Limiting on /auth/login
**Objective**: Verify rate limiting prevents email spam and brute force attacks

**Prerequisites**: Rate limiting middleware should be configured (check if it exists)

**Steps**:
1. Send login request: `POST /api/auth/login` with email
2. Send 2nd request immediately with same email
3. Send 3rd, 4th, 5th requests in rapid succession
4. Inspect responses:
   - First few requests should succeed (202)
   - After threshold (e.g., 5 requests per minute), should receive 429 Too Many Requests
5. Wait for rate limit window to expire (1-5 minutes)
6. **Verify**: Can make new request
7. Test with different emails (should have separate rate limit buckets):
   - Verify attacker cannot bypass by rotating emails
   - Or verify global rate limit per IP

**Expected Results**:
- Rate limiting is enforced per IP or per email
- Prevents spam and brute force attacks
- Returns 429 with Retry-After header
- Window expires and requests can resume

**Note**: If rate limiting is not currently implemented, recommend adding:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@router.post("/auth/login", status_code=202)
@limiter.limit("5/minute")  # 5 requests per minute per IP
async def login(request: Request, req: LoginRequest, db: AsyncSession):
    ...
```

---

### Test Case 4.4: Token Expiration Enforced on Backend
**Objective**: Verify backend properly rejects expired tokens

**Steps**:
1. Create a token with current time
2. Immediately check it via `/api/auth/login-status/{token}`
3. **Verify**: Returns `{valid: true, ...}`
4. Wait for 15+ minutes (or manually modify DB)
5. Check same token again
6. **Verify**: Returns `{valid: false, reason: "expired"}`
7. Attempt to use expired token via `/api/auth/verify`
8. **Verify**: Returns 400 Bad Request: "Login link invalid or expired"
9. Verify database timestamp is in UTC timezone consistently
10. Test with server time skew (if possible) to ensure timezone handling

**Expected Results**:
- Expiration is strictly enforced on backend
- Client-side checks are not relied upon
- Timezone handling is correct (all times in UTC)
- No off-by-one errors in expiration checks

---

### Test Case 4.5: Password Security (Not Applicable)
**Objective**: N/A — This is passwordless authentication

**Note**: Email login removes password security concerns. Focus instead on:
- Email account security (user's email should use strong password)
- Link expiration (15 minutes)
- One-time-use enforcement
- No ability to guess tokens (cryptographically random)

---

## 5. UX Testing

### Test Case 5.1: Loading States & Animations
**Objective**: Verify smooth, professional loading experience

**Steps**:
1. On EmailLoginPage:
   - Enter email and click "Send Login Link"
   - **Verify**: Button shows spinner (CSS animated, not loading.gif)
   - **Verify**: Text changes to "Sending link…"
   - **Verify**: Email input is disabled (grayed out)
   - **Verify**: Transition is smooth (~0.3s)
2. After receiving email, click link:
   - **Verify**: VerifyTokenPage shows centered spinner
   - **Verify**: Spinner rotates smoothly (60 FPS if browser capable)
   - **Verify**: Text reads "Verifying your login link…"
   - **Verify**: No text flickering or jumping
3. Upon success:
   - **Verify**: Spinner transitions to CheckCircle icon
   - **Verify**: "Login successful!" text appears
   - **Verify**: Brief pause (1.5-2 sec) before redirect
   - **Verify**: Redirect to `/my-requests` is smooth (no white flash)

**Expected Results**:
- All animations are CSS-based (not JavaScript setInterval)
- Loading states feel responsive (< 100ms perceived latency)
- Transitions use appropriate easing functions (ease-in-out)
- No layout shift (CLS = Cumulative Layout Shift near 0)

---

### Test Case 5.2: Error Messages & Clarity
**Objective**: Verify error messages are clear and actionable

**Manual test scenarios**:

1. **Expired token**:
   - Error: "This login link has expired. Login links are valid for 15 minutes."
   - CTA: "Request new login link" button
   - **Verify**: User understands they need to request a new link

2. **Already-used token**:
   - Error: "This login link was already used. If that wasn't you, request a new one."
   - CTA: "Request new login link" button
   - **Verify**: User knows not to worry if they used it themselves, but to act if suspicious

3. **Invalid/malformed token**:
   - Error: "This login link is invalid or not found."
   - CTA: "Try again" button
   - **Verify**: Umbrella error for various invalid states

4. **Network error**:
   - Error: "Network error. Please try again."
   - **Verify**: Shows during fetch failures (no internet, server down)

5. **Missing email on signup**:
   - Error: "display_name is required for new signups"
   - CTA: Show form asking for display name
   - **Verify**: User knows what to do next

**Expected Results**:
- All errors include actionable guidance
- Error messages do not expose technical details (no stack traces)
- CTAs (buttons) are always present to move user forward
- Color coding: red for errors, amber for expiration, blue for already-used

---

### Test Case 5.3: Links Work Across Devices & Email Clients
**Objective**: Verify magic links function across various email clients and devices

**Manual test across platforms**:

1. **Desktop email clients**:
   - Gmail (browser)
   - Outlook (browser)
   - Apple Mail
   - Thunderbird
   - **Verify**: Link is clickable and opens in browser

2. **Mobile email clients**:
   - Gmail (iOS)
   - Gmail (Android)
   - Apple Mail (iOS)
   - Outlook (iOS/Android)
   - **Verify**: Link opens in system browser correctly

3. **Webmail**:
   - Gmail web
   - Outlook web
   - **Verify**: Link preview and click both work

4. **Email link handling**:
   - Click link in email client → Should open in default browser
   - Open link in different browser than email client
   - **Verify**: Token still works (not tied to browser)
   - **Verify**: Deep link works: `https://app.example.com/auth/email-verify?token=xyz`

5. **URL encoding**:
   - Token contains special characters (unlikely with token_urlsafe)
   - **Verify**: URL encoding is correct and email clients handle it

**Expected Results**:
- Links work universally across email clients
- Token is preserved during email rendering
- No URL encoding issues causing token corruption
- Works across different browsers/devices

---

### Test Case 5.4: Mobile Responsive Login Page
**Objective**: Verify login pages are mobile-friendly

**Test on devices/viewports**:

1. **iPhone SE (375px width)**:
   - Landscape and portrait
   - **Verify**: Form is readable without horizontal scroll
   - **Verify**: Buttons are touch-friendly (≥44px height)
   - **Verify**: Text doesn't overflow
   - **Verify**: Logo/branding is visible

2. **iPad (768px width)**:
   - Landscape and portrait
   - **Verify**: Page is not stretched
   - **Verify**: Form width is reasonable (not too wide)

3. **Desktop (1920px width)**:
   - **Verify**: Form doesn't stretch to full width
   - **Verify**: Form is centered and capped at ~500px max-width
   - **Verify**: Comfortable spacing around form

4. **Touch interactions**:
   - Email input field should have proper focus states
   - Buttons should have `:active` and `:focus` states
   - Form should allow easy tap-to-submit

5. **Keyboard navigation** (mobile on-screen keyboard):
   - Enter email → keyboard appears
   - Type email → keyboard doesn't cover submit button
   - Submit button is reachable without keyboard dismissal
   - **Verify**: UX is smooth on touch keyboard

**Expected Results**:
- Page is fully responsive down to 320px width
- Touch targets are ≥44x44px
- No horizontal scrolling needed
- Mobile-optimized spacing and fonts

---

## 6. Automated Test Suite

### Test Files to Create/Update

**File**: `/backend/tests/test_email_auth_integration.py`

```python
"""Integration tests for email authentication workflow."""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.email_auth import login, verify, login_status
from app.models.auth import LoginToken
from app.models.request import User
from app.services.token_service import TokenService

class TestEmailAuthIntegration:
    """Integration tests for complete email auth workflow."""

    @pytest.mark.asyncio
    async def test_complete_new_user_signup_flow(self, db_session: AsyncSession):
        """Test complete signup flow: login → verify → authenticated."""
        email = "newuser@test.com"
        
        # Step 1: Request login link
        response = await login(LoginRequest(email=email), db_session)
        assert response["status"] == "sent"
        
        # Step 2: Retrieve token from DB
        result = await db_session.execute(
            select(LoginToken).where(LoginToken.email == email)
        )
        token = result.scalar_one()
        assert token is not None
        assert token.user_id is None  # New user
        
        # Step 3: Check token status (frontend would do this)
        status = await login_status(token.token, db_session)
        assert status.valid is True
        assert status.email == email
        
        # Step 4: Verify token and create user
        verify_response = await verify(
            VerifyRequest(token=token.token, display_name="Test User"),
            db_session
        )
        assert verify_response.email == email
        assert verify_response.user_id is not None
        
        # Step 5: Verify user was created
        result = await db_session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one()
        assert user.display_name == "Test User"
        assert user.email_verified is True
        assert "Requestor" in user.roles

    @pytest.mark.asyncio
    async def test_complete_existing_user_login_flow(
        self, db_session: AsyncSession, user: User
    ):
        """Test login flow for existing user."""
        # Step 1: Request login link
        response = await login(LoginRequest(email=user.email), db_session)
        assert response["status"] == "sent"
        
        # Step 2: Verify token (no display_name needed)
        result = await db_session.execute(
            select(LoginToken).where(LoginToken.email == user.email)
        )
        token = result.scalar_one()
        
        verify_response = await verify(VerifyRequest(token=token.token), db_session)
        assert verify_response.user_id == str(user.id)
        assert verify_response.email == user.email

    @pytest.mark.asyncio
    async def test_token_cannot_be_reused(self, db_session: AsyncSession):
        """Verify one-time-use constraint."""
        email = "reuse_test@test.com"
        service = TokenService()
        token = await service.create_login_token(db_session, email)
        await db_session.flush()
        
        # First verification succeeds
        verify_response = await verify(VerifyRequest(token=token.token), db_session)
        assert verify_response.email == email
        
        # Second verification fails
        with pytest.raises(HTTPException) as exc:
            await verify(VerifyRequest(token=token.token), db_session)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_multiple_login_requests_invalidate_previous(
        self, db_session: AsyncSession
    ):
        """Verify only 1 active token per email."""
        email = "multi@test.com"
        service = TokenService()
        
        # First token
        token1 = await service.create_login_token(db_session, email)
        await db_session.flush()
        
        # Second token invalidates first
        token2 = await service.create_login_token(db_session, email)
        await db_session.flush()
        
        # Refresh and check
        await db_session.refresh(token1)
        assert token1.used_at is not None  # Marked as used (invalidated)
        assert token2.used_at is None
        
        # First token fails validation
        validated = await service.validate_login_token(db_session, token1.token)
        assert validated is None
        
        # Second token passes
        validated = await service.validate_login_token(db_session, token2.token)
        assert validated is not None

    @pytest.mark.asyncio
    async def test_new_signup_without_display_name_fails(
        self, db_session: AsyncSession
    ):
        """Verify display_name is required for new signups."""
        email = "nodisplayname@test.com"
        service = TokenService()
        token = await service.create_login_token(db_session, email)
        await db_session.flush()
        
        # Attempt to verify without display_name
        with pytest.raises(HTTPException) as exc:
            await verify(VerifyRequest(token=token.token), db_session)
        assert exc.value.status_code == 422
        assert "display_name" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_rate_limiting_on_login(self, db_session: AsyncSession):
        """Test that rapid login requests are rate-limited."""
        # TODO: Implement once rate limiting middleware is added
        # Should verify 429 Too Many Requests after threshold
        pass

    @pytest.mark.asyncio
    async def test_email_enumeration_protection(self, db_session: AsyncSession):
        """Verify identical response for existing and non-existing emails."""
        existing_email = "existing@test.com"
        user = User(email=existing_email, display_name="Existing")
        db_session.add(user)
        await db_session.flush()
        
        # Both should return 202
        response_existing = await login(LoginRequest(email=existing_email), db_session)
        response_nonexistent = await login(
            LoginRequest(email="fake@test.com"), db_session
        )
        
        assert response_existing["status"] == "sent"
        assert response_nonexistent["status"] == "sent"
        # Identical message to prevent enumeration
        assert response_existing["message"] == response_nonexistent["message"]
```

---

### Frontend Component Tests

**File**: `/frontend/src/pages/__tests__/EmailLoginPage.test.tsx`

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmailLoginPage } from '../EmailLoginPage'

describe('EmailLoginPage', () => {
  it('should send login link when form is submitted', async () => {
    render(<EmailLoginPage />)
    
    const emailInput = screen.getByPlaceholderText(/you@example.com/i)
    const submitButton = screen.getByRole('button', { name: /send login link/i })
    
    await userEvent.type(emailInput, 'test@example.com')
    await userEvent.click(submitButton)
    
    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument()
    })
  })

  it('should show loading state during submission', async () => {
    render(<EmailLoginPage />)
    
    const emailInput = screen.getByPlaceholderText(/you@example.com/i)
    const submitButton = screen.getByRole('button', { name: /send login link/i })
    
    await userEvent.type(emailInput, 'test@example.com')
    await userEvent.click(submitButton)
    
    expect(submitButton).toBeDisabled()
    expect(screen.getByText(/sending link/i)).toBeInTheDocument()
  })

  it('should validate email format', async () => {
    render(<EmailLoginPage />)
    
    const emailInput = screen.getByPlaceholderText(/you@example.com/i)
    const submitButton = screen.getByRole('button', { name: /send login link/i })
    
    // Invalid email
    await userEvent.type(emailInput, 'invalid')
    expect(submitButton).toBeDisabled()
    
    // Clear and enter valid email
    await userEvent.clear(emailInput)
    await userEvent.type(emailInput, 'valid@example.com')
    expect(submitButton).not.toBeDisabled()
  })

  it('should handle network errors gracefully', async () => {
    global.fetch = jest.fn(() =>
      Promise.reject(new Error('Network error'))
    )
    
    render(<EmailLoginPage />)
    
    const emailInput = screen.getByPlaceholderText(/you@example.com/i)
    const submitButton = screen.getByRole('button', { name: /send login link/i })
    
    await userEvent.type(emailInput, 'test@example.com')
    await userEvent.click(submitButton)
    
    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument()
    })
  })
})
```

**File**: `/frontend/src/pages/__tests__/VerifyTokenPage.test.tsx`

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { VerifyTokenPage } from '../VerifyTokenPage'

describe('VerifyTokenPage', () => {
  it('should show loading state initially', () => {
    // Mock useSearchParams to return a token
    jest.mock('react-router-dom', () => ({
      ...jest.requireActual('react-router-dom'),
      useSearchParams: () => [new URLSearchParams({ token: 'valid_token' })]
    }))
    
    render(
      <BrowserRouter>
        <VerifyTokenPage />
      </BrowserRouter>
    )
    
    expect(screen.getByText(/verifying your login link/i)).toBeInTheDocument()
  })

  it('should show success message when token is valid', async () => {
    global.fetch = jest.fn((url) => {
      if (url.includes('/login-status/')) {
        return Promise.resolve({
          json: () => Promise.resolve({ valid: true, email: 'test@example.com' })
        })
      }
      return Promise.resolve({
        json: () => Promise.resolve({
          user_id: '123',
          email: 'test@example.com',
          display_name: 'Test User',
          access_token: 'jwt_token'
        })
      })
    })
    
    render(
      <BrowserRouter>
        <VerifyTokenPage />
      </BrowserRouter>
    )
    
    await waitFor(() => {
      expect(screen.getByText(/login successful/i)).toBeInTheDocument()
    })
  })

  it('should show expired message when token is expired', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ valid: false, reason: 'expired' })
      })
    )
    
    render(
      <BrowserRouter>
        <VerifyTokenPage />
      </BrowserRouter>
    )
    
    await waitFor(() => {
      expect(screen.getByText(/login link expired/i)).toBeInTheDocument()
      expect(screen.getByText(/15 minutes/i)).toBeInTheDocument()
    })
  })

  it('should show already-used message when token was consumed', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ valid: false, reason: 'already_used' })
      })
    )
    
    render(
      <BrowserRouter>
        <VerifyTokenPage />
      </BrowserRouter>
    )
    
    await waitFor(() => {
      expect(screen.getByText(/link already used/i)).toBeInTheDocument()
    })
  })

  it('should redirect to /my-requests on successful login', async () => {
    const mockNavigate = jest.fn()
    jest.mock('react-router-dom', () => ({
      ...jest.requireActual('react-router-dom'),
      useNavigate: () => mockNavigate
    }))
    
    global.fetch = jest.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({
          user_id: '123',
          email: 'test@example.com',
          display_name: 'Test User',
          access_token: 'jwt_token'
        })
      })
    )
    
    render(
      <BrowserRouter>
        <VerifyTokenPage />
      </BrowserRouter>
    )
    
    await waitFor(() => {
      expect(screen.getByText(/login successful/i)).toBeInTheDocument()
    })
    
    // Should redirect after delay
    await waitFor(
      () => {
        expect(localStorage.getItem('accessToken')).toBe('jwt_token')
      },
      { timeout: 2000 }
    )
  })
})
```

---

## 7. Performance & Load Testing (Optional)

### Test Case 7.1: Token Generation Performance
**Objective**: Verify token generation is fast (< 1ms per token)

**Automated Test**:
```python
import time

def test_token_generation_performance():
    """Verify token generation is sub-millisecond."""
    service = TokenService()
    
    start = time.perf_counter()
    for _ in range(1000):
        service.generate_token()
    elapsed = time.perf_counter() - start
    
    avg_per_token = (elapsed / 1000) * 1000  # Convert to ms
    assert avg_per_token < 1.0, f"Token generation too slow: {avg_per_token}ms"
```

### Test Case 7.2: Email Sending Latency
**Objective**: Verify email sends complete within SLA (< 5 seconds)

**Steps**:
1. Send login request and time the response
2. Email should be sent asynchronously (non-blocking)
3. `/api/auth/login` should return 202 within 200-500ms (not waiting for email)
4. Email delivery itself may take seconds (external service), but frontend doesn't wait
5. **Verify**: Response is fast despite email sending

---

## 8. Checklist for Test Execution

### Pre-Test Setup
- [ ] Database is clean (migrations run, no test data)
- [ ] Backend server is running (http://localhost:8000)
- [ ] Frontend server is running (http://localhost:5173)
- [ ] Email service is configured (SMTP or Graph API)
- [ ] Redis is running (if required)
- [ ] Test data fixtures are loaded (if needed)

### Manual Testing Checklist
- [ ] Test Case 1.1: New user signup (happy path)
- [ ] Test Case 1.2: Existing user login
- [ ] Test Case 1.3: Loading states feel smooth
- [ ] Test Case 2.1: Expired token (16+ minutes)
- [ ] Test Case 2.2: Already-used token (clicking twice)
- [ ] Test Case 2.3: Invalid/malformed token
- [ ] Test Case 2.4: Email not found (enumeration protection)
- [ ] Test Case 2.5: Multiple requests invalidate previous tokens
- [ ] Test Case 3.1: Login → MY REQUESTS
- [ ] Test Case 3.2: Login → View conversation threads
- [ ] Test Case 3.3: Login → Add comments with mentions
- [ ] Test Case 3.4: Logout flow
- [ ] Test Case 4.1: Token format (URL-safe, no info leak)
- [ ] Test Case 4.2: CSRF protection
- [ ] Test Case 4.3: Rate limiting (if implemented)
- [ ] Test Case 4.4: Token expiration enforced
- [ ] Test Case 5.1: Loading animations smooth
- [ ] Test Case 5.2: Error messages clear and actionable
- [ ] Test Case 5.3: Links work across email clients/devices
- [ ] Test Case 5.4: Mobile responsive (iPhone, iPad, Desktop)

### Automated Testing Checklist
- [ ] Run all unit tests: `pytest backend/tests/test_email_auth.py -v`
- [ ] Run integration tests: `pytest backend/tests/test_email_auth_integration.py -v`
- [ ] Run frontend component tests: `npm test -- EmailLoginPage VerifyTokenPage`
- [ ] Run full test suite: `pytest backend/tests/` -v
- [ ] Check code coverage: `pytest --cov=app.api.email_auth --cov=app.services.token_service`

---

## 9. Success Criteria

### Manual Testing Success
✓ All 20 manual test cases pass without critical issues
✓ No authentication errors (401/403) for valid users
✓ Error messages are clear and actionable
✓ Mobile experience is smooth and responsive
✓ Email links work across all major email clients
✓ No SQL injection or XSS vulnerabilities discovered
✓ Token expiration is enforced on backend

### Automated Testing Success
✓ All unit tests pass (test_email_auth.py)
✓ All integration tests pass (test_email_auth_integration.py)
✓ All frontend component tests pass
✓ Code coverage > 85% for auth modules
✓ No failing security linting checks

### Performance Success
✓ Token generation < 1ms per token
✓ Login endpoint responds < 500ms
✓ Email links load in < 2 seconds
✓ Redirects are smooth (< 500ms)

### Security Success
✓ No plaintext sensitive data in tokens
✓ Email enumeration protection verified
✓ One-time-use constraint enforced
✓ Token expiration enforced on backend
✓ CORS/CSRF protections in place

---

## 10. Known Issues & Future Improvements

### Current Implementation Notes
1. **JWT Signing**: Currently using base64-encoded payload (placeholder). Should implement proper JWT with RS256 or HS256 signing in production.
2. **Rate Limiting**: Not yet implemented on `/auth/login`. Should add slowapi or similar middleware.
3. **Token Hashing**: Tokens are stored plaintext in DB. Could hash for additional security (not critical for 15-min expiry).
4. **Email Delivery**: Non-blocking but failures are logged. Could add retry logic or webhook confirmation.
5. **Display Name**: Currently required for new signups. Could collect in separate onboarding step.

### Recommended Future Tests
- [ ] Test with very long email addresses (255+ chars)
- [ ] Test with Unicode characters in display_name
- [ ] Test password reset flow (if added later)
- [ ] Test two-factor authentication (if added later)
- [ ] Test session persistence across browser tabs
- [ ] Test concurrent login attempts from same user
- [ ] Load test: 1000+ concurrent login requests
- [ ] Test email client rendering (Litmus/Email on Acid)

---

## 11. Test Environment Configuration

### Local Development
```bash
# Backend
cd backend
source venv/bin/activate
export DATABASE_URL=sqlite:///./test.db
export REDIS_URL=redis://localhost:6379
export EMAIL_BACKEND=smtp  # or console for testing
export SMTP_HOST=localhost
export SMTP_PORT=1025  # MailHog or similar
python -m pytest tests/

# Frontend
cd frontend
npm test -- --coverage
npm run dev
```

### Test Email Service (Local)
```bash
# Using MailHog for local email testing
docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog

# Access UI: http://localhost:8025
```

### Staging Environment
- Use real email service (Microsoft Graph or SendGrid)
- Use staging database with test users
- Run full automated test suite before each deploy
- Perform smoke test: complete login flow at least once

---

## 12. Test Reports & Sign-Off

### Report Template
```
Test Execution Report
Date: [DATE]
Tester: [NAME]
Environment: [LOCAL/STAGING/PRODUCTION]

Summary:
- Total Test Cases: 20 manual + 8 automated
- Passed: [X]
- Failed: [X]
- Blocked: [X]

Critical Issues:
[List any blockers or showstoppers]

Minor Issues:
[List any non-critical bugs]

Recommendations:
[List improvements or follow-ups]

Sign-off: [ ] Ready for Production
```

---

## End of Testing Plan
