# Email Login Integration Guide

## Required Changes

Two files need to be updated to complete the email login implementation:

### 1. Update useAuth.ts

**Location:** `src/hooks/useAuth.ts`

**Current state:** MSAL-only authentication

**Required changes:**
1. Import the auth utilities at the top
2. Add JWT token state detection
3. Update token getter to support JWT
4. Update logout to handle JWT cleanup
5. Add token expiry monitoring hook

**Exact changes:**

#### Line 20: Add import
```typescript
import { clearAuthStorage, setupTokenExpiryHandler } from '@/lib/auth'
```

#### Line 25 (after useMsal() calls): Add JWT state
```typescript
  // ── JWT auth state ──────────────────────────────────────────────────────────
  // Check localStorage for JWT token from email login flow
  const jwtToken = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null
  const isJwtAuthenticated = !!jwtToken
```

#### Line 35 (in setTokenGetter useEffect): Replace token getter logic
**OLD:**
```typescript
    setTokenGetter(async () => {
      const account = instance.getActiveAccount() ?? accounts[0]
      if (!account) return null
      try {
        const result = await instance.acquireTokenSilent({ ...loginRequest, account })
        return result.accessToken
      } catch {
        // Silent renewal failed (e.g. session expired) — redirect to re-auth
        await instance.acquireTokenRedirect({ ...loginRequest, account })
        return null
      }
    })
```

**NEW:**
```typescript
    // Priority: MSAL > JWT > none
    if (msalAuthenticated && accounts.length > 0) {
      setTokenGetter(async () => {
        const account = instance.getActiveAccount() ?? accounts[0]
        if (!account) return null
        try {
          const result = await instance.acquireTokenSilent({ ...loginRequest, account })
          return result.accessToken
        } catch {
          await instance.acquireTokenRedirect({ ...loginRequest, account })
          return null
        }
      })
    } else if (isJwtAuthenticated) {
      setTokenGetter(async () => jwtToken)
    } else {
      setTokenGetter(async () => null)
    }
```

#### Line 45 (in useEffect dependencies): Add JWT dependencies
**OLD:**
```typescript
  }, [instance, accounts])
```

**NEW:**
```typescript
  }, [instance, accounts, msalAuthenticated, isJwtAuthenticated, jwtToken])
```

#### Line 50 (in useQuery enabled): Update condition
**OLD:**
```typescript
    enabled: SKIP_AUTH ? true : (msalAuthenticated && !msalLoading),
```

**NEW:**
```typescript
    enabled: SKIP_AUTH ? true : (msalAuthenticated || isJwtAuthenticated),
```

#### Line 65 (in isLoading calculation): Update condition
**OLD:**
```typescript
  const isLoading = SKIP_AUTH ? isLoadingUser : (msalLoading || (msalAuthenticated && isLoadingUser))
```

**NEW:**
```typescript
  const isLoading = SKIP_AUTH
    ? isLoadingUser
    : msalLoading || ((msalAuthenticated || isJwtAuthenticated) && isLoadingUser)
```

#### Line 70 (in isAuthenticated calculation): Update condition
**OLD:**
```typescript
  const isAuthenticated = SKIP_AUTH ? true : msalAuthenticated
```

**NEW:**
```typescript
  const isAuthenticated = SKIP_AUTH ? true : (msalAuthenticated || isJwtAuthenticated)
```

#### Line 75 (login/logout functions): Add useCallback and update logout
**OLD:**
```typescript
  const login = () => { if (!SKIP_AUTH) instance.loginRedirect(loginRequest) }
  const logout = () => {
    if (!SKIP_AUTH) instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin })
  }
```

**NEW:**
```typescript
  const login = useCallback(() => {
    if (!SKIP_AUTH) {
      instance.loginRedirect(loginRequest)
    }
  }, [instance])

  const logout = useCallback(() => {
    if (SKIP_AUTH) return

    // Clear JWT if present (email login)
    if (isJwtAuthenticated) {
      clearAuthStorage()
      window.location.href = '/login'
      return
    }

    // Otherwise MSAL logout (Azure AD)
    instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin })
  }, [instance, isJwtAuthenticated])
```

#### Line 85 (add token expiry monitoring): Add new useEffect after logout
```typescript
  // ── Token expiry monitoring ─────────────────────────────────────────────────
  // Auto-logout 5 minutes before JWT expires
  useEffect(() => {
    if (!jwtToken) return

    const cleanup = setupTokenExpiryHandler(jwtToken, () => {
      clearAuthStorage()
      // Force reload to trigger re-auth
      window.location.href = '/login'
    })

    return cleanup
  }, [jwtToken])
```

#### Add useCallback import
**Add to line 1:**
```typescript
import { useEffect, useCallback } from 'react'
```

### 2. Update router/index.tsx

**Location:** `src/router/index.tsx`

**Current state:** Routes for LoginPage, respond, and authenticated pages

**Required changes:**
1. Import the new email login components
2. Add two new public routes

**Exact changes:**

#### Line 6: Add component imports
```typescript
import { EmailLoginPage } from '@/pages/EmailLoginPage'
import { VerifyTokenPage } from '@/pages/VerifyTokenPage'
```

#### Line 57 (in Routes section, after /login route): Add email routes
```typescript
      <Route path="/email-login" element={<EmailLoginPage />} />
      <Route path="/login/verify" element={<VerifyTokenPage />} />
```

**Result:** The public routes section should look like:
```typescript
    <Routes>
      {/* Fully public — no auth required */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/email-login" element={<EmailLoginPage />} />
      <Route path="/login/verify" element={<VerifyTokenPage />} />
      <Route path="/respond/:id" element={<RespondPage />} />
      
      {/* Authenticated — wrapped in AppShell */}
      ...
```

## Verification Checklist

After making changes:

- [ ] TypeScript compilation passes
- [ ] No import errors
- [ ] LoginPage renders with both Microsoft and Email buttons
- [ ] Can navigate to /email-login
- [ ] Can navigate to /login/verify?token=test
- [ ] useAuth returns correct isAuthenticated state
- [ ] No console errors

## Testing Flow

1. **Email submission:**
   - Visit `/email-login`
   - Enter valid email
   - Submit form
   - Should show "Check your email"
   - Check network tab: POST /api/auth/login should return 202

2. **Token verification:**
   - Navigate to `/login/verify?token=test_token`
   - Should show "Verifying your login link..."
   - Check network: GET /api/auth-login-status/test_token
   - If token valid: POST /api/auth/verify should be called
   - localStorage should have accessToken key
   - Should redirect to /my-requests

3. **Error states:**
   - Test with expired token
   - Test with invalid token
   - Test with already-used token
   - Each should show appropriate error message

4. **MSAL still works:**
   - Visit /login
   - Should see both Microsoft and Email options
   - Microsoft button should still work
   - Can login via MSAL as before

5. **JWT handling:**
   - After email login, check localStorage
   - accessToken should be set
   - currentUser should be set
   - Logout should clear both

## File References

- Full useAuth.ts code: See CODE_SNIPPETS.md
- Full router code: See CODE_SNIPPETS.md
- Components created: EmailLoginPage.tsx, VerifyTokenPage.tsx, auth.ts

## Common Issues

**Issue:** LoginPage doesn't show email option
- Check that LoginPage.tsx was updated with email button
- Verify browser cache is cleared

**Issue:** Token verification fails
- Check backend is running
- Verify /api/auth/login-status endpoint exists
- Check browser console for fetch errors

**Issue:** useAuth returns isAuthenticated=false
- Verify localStorage has accessToken key
- Check that setTokenGetter is being called
- Verify VITE_SKIP_AUTH is not interfering

**Issue:** Redirect doesn't happen
- Check that /my-requests route is accessible
- Verify RequireAuth component is working
- Check for JavaScript errors in console

## Rollback Plan

If issues occur after deployment:

1. Remove email option from LoginPage
2. Disable /email-login and /login/verify routes
3. Revert useAuth.ts changes
4. Users can continue with MSAL login
5. Data is not affected (only UI/auth flow)

## Performance Notes

- No new npm dependencies
- Minimal bundle size increase (~16 KB)
- localStorage read on every useAuth call (negligible)
- JWT decode is synchronous (client-side only)
- Token expiry check runs once per JWT

## Browser Compatibility

Tested on:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

Requires:
- fetch API
- localStorage
- URLSearchParams (for token parsing)
- JavaScript ES2020+
