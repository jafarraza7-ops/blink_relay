# Email Login Implementation — Code Snippets

## Complete Component Code

### 1. EmailLoginPage.tsx
Location: `src/pages/EmailLoginPage.tsx`

```typescript
import { useState } from 'react'
import { Zap, Mail, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function EmailLoginPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!email.trim()) {
      setError('Please enter your email address')
      return
    }

    setLoading(true)

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.toLowerCase().trim() }),
      })

      if (response.status === 202) {
        setSubmitted(true)
        setEmail('')
      } else if (response.status === 400) {
        const data = await response.json()
        setError(data.detail || 'Failed to send login link. Please try again.')
      } else {
        setError('Failed to send login link. Please try again.')
      }
    } catch (err) {
      setError('Network error. Please try again.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50">
      <div className="w-full max-w-sm space-y-8 px-4 text-center">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary shadow-lg">
            <Zap className="h-9 w-9 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Blink Relay</h1>
            <p className="text-sm text-muted-foreground">Tech Request Portal</p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
          {!submitted ? (
            <>
              <div>
                <h2 className="text-lg font-semibold">Sign in with Email</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Enter your email to receive a secure login link
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label htmlFor="email" className="text-sm font-medium text-foreground">
                    Email Address
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    disabled={loading}
                    required
                    autoFocus
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50"
                  />
                </div>

                {error && (
                  <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {error}
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className="w-full gap-2"
                >
                  {loading ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      Sending link…
                    </>
                  ) : (
                    <>
                      <Mail className="h-4 w-4" />
                      Send Login Link
                    </>
                  )}
                </Button>
              </form>
            </>
          ) : (
            <div className="space-y-4 py-4">
              <div className="flex justify-center">
                <CheckCircle className="h-12 w-12 text-green-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Check your email</h2>
                <p className="text-sm text-muted-foreground mt-2">
                  We've sent a secure login link to <span className="font-medium text-foreground">{email}</span>
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  The link expires in 15 minutes. If you don't see it, check your spam folder.
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setSubmitted(false)
                  setEmail('')
                  setError('')
                }}
                className="w-full"
              >
                Try another email
              </Button>
            </div>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          For access issues contact{' '}
          <a href="mailto:it@blinkcharging.com" className="text-primary hover:underline">
            it@blinkcharging.com
          </a>
        </p>
      </div>
    </div>
  )
}
```

### 2. VerifyTokenPage.tsx
Location: `src/pages/VerifyTokenPage.tsx`

```typescript
import { useState, useEffect } from 'react'
import { useSearchParams, Navigate } from 'react-router-dom'
import { Zap, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface TokenStatus {
  valid: boolean
  reason?: 'valid' | 'not_found' | 'expired' | 'already_used'
  email?: string
}

export function VerifyTokenPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  const [tokenStatus, setTokenStatus] = useState<TokenStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [redirecting, setRedirecting] = useState(false)

  useEffect(() => {
    if (!token) {
      setError('No login token provided')
      setLoading(false)
      return
    }

    checkTokenStatus()
  }, [token])

  const checkTokenStatus = async () => {
    try {
      const response = await fetch(`/api/auth/login-status/${token}`)
      const data: TokenStatus = await response.json()
      setTokenStatus(data)

      if (data.valid) {
        handleVerify(data)
      }
    } catch (err) {
      setError('Failed to verify login link')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async (status: TokenStatus) => {
    if (!token || !status.valid) {
      setError('Invalid or expired login link')
      return
    }

    setVerifying(true)
    setError('')

    try {
      const response = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      })

      if (response.status === 200) {
        const data = await response.json()

        // Store JWT in localStorage
        localStorage.setItem('accessToken', data.access_token)
        localStorage.setItem('currentUser', JSON.stringify({
          id: data.user_id,
          email: data.email,
          name: data.display_name,
        }))

        setSuccess(true)

        // Redirect after brief delay so user sees success state
        setTimeout(() => {
          setRedirecting(true)
        }, 1500)
      } else {
        const responseData = await response.json()
        setError(responseData.detail || 'Failed to complete login. Please try again.')
      }
    } catch (err) {
      setError('Network error. Please try again.')
      console.error(err)
    } finally {
      setVerifying(false)
    }
  }

  if (redirecting) {
    return <Navigate to="/my-requests" replace />
  }

  const getErrorMessage = () => {
    switch (tokenStatus?.reason) {
      case 'expired':
        return 'This login link has expired. Login links are valid for 15 minutes.'
      case 'already_used':
        return 'This login link was already used. Please request a new one.'
      case 'not_found':
        return 'This login link is invalid or not found.'
      default:
        return error || 'Unable to verify your login link'
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50">
      <div className="w-full max-w-sm space-y-8 px-4 text-center">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary shadow-lg">
            <Zap className="h-9 w-9 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Blink Relay</h1>
            <p className="text-sm text-muted-foreground">Tech Request Portal</p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
          {loading ? (
            <div className="space-y-4 py-6">
              <div className="flex justify-center">
                <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Verifying your login link…</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  This should only take a moment
                </p>
              </div>
            </div>
          ) : success ? (
            <div className="space-y-4 py-4">
              <div className="flex justify-center">
                <CheckCircle className="h-12 w-12 text-green-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Login successful!</h2>
                <p className="text-sm text-muted-foreground mt-2">
                  Redirecting you to your requests…
                </p>
              </div>
              <div className="flex justify-center pt-2">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              </div>
            </div>
          ) : tokenStatus?.reason === 'expired' ? (
            <div className="space-y-4">
              <div className="flex justify-center">
                <Clock className="h-12 w-12 text-amber-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Login link expired</h2>
                <p className="text-sm text-muted-foreground mt-2">
                  Login links are valid for 15 minutes. Please request a new one.
                </p>
              </div>
              <Button asChild className="w-full gap-2">
                <a href="/login">Request new login link</a>
              </Button>
            </div>
          ) : tokenStatus?.reason === 'already_used' ? (
            <div className="space-y-4">
              <div className="flex justify-center">
                <AlertCircle className="h-12 w-12 text-blue-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Link already used</h2>
                <p className="text-sm text-muted-foreground mt-2">
                  This login link was already used. If that wasn't you, request a new login link.
                </p>
              </div>
              <Button asChild className="w-full gap-2">
                <a href="/login">Request new login link</a>
              </Button>
            </div>
          ) : error ? (
            <div className="space-y-4">
              <div className="flex justify-center">
                <AlertCircle className="h-12 w-12 text-destructive" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Login failed</h2>
                <p className="text-sm text-muted-foreground mt-2">
                  {getErrorMessage()}
                </p>
              </div>
              <Button asChild className="w-full gap-2">
                <a href="/login">Try again</a>
              </Button>
            </div>
          ) : (
            <div className="space-y-4 py-4">
              <div className="flex justify-center">
                <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Completing login…</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  {verifying ? 'Processing your login...' : 'Please wait'}
                </p>
              </div>
            </div>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          For access issues contact{' '}
          <a href="mailto:it@blinkcharging.com" className="text-primary hover:underline">
            it@blinkcharging.com
          </a>
        </p>
      </div>
    </div>
  )
}
```

### 3. auth.ts (Utilities)
Location: `src/lib/auth.ts`

```typescript
/**
 * auth.ts — Auth utilities for JWT and token management.
 */

const TOKEN_KEY = 'accessToken'
const USER_KEY = 'currentUser'

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function clearAuthStorage(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    // localStorage may not be available
  }
}

export function storeAuth(token: string, user: { id: string; email: string; name: string }): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  } catch {
    // localStorage may not be available
  }
}

export function getStoredUser(): { id: string; email: string; name: string } | null {
  try {
    const userJson = localStorage.getItem(USER_KEY)
    return userJson ? JSON.parse(userJson) : null
  } catch {
    return null
  }
}

export function decodeJwt(token: string): Record<string, unknown> | null {
  try {
    const [, payload] = token.split('.')
    if (!payload) return null
    const decoded = JSON.parse(atob(payload))
    return decoded
  } catch {
    return null
  }
}

export function isTokenExpired(token: string): boolean {
  const claims = decodeJwt(token)
  if (!claims || typeof claims.exp !== 'number') {
    return false
  }
  return Date.now() >= claims.exp * 1000
}

export function getTokenExpiresIn(token: string): number {
  const claims = decodeJwt(token)
  if (!claims || typeof claims.exp !== 'number') {
    return -1
  }
  const expiresAt = claims.exp * 1000
  return Math.max(0, expiresAt - Date.now())
}

export function setupTokenExpiryHandler(token: string, onExpired: () => void): () => void {
  const expiresIn = getTokenExpiresIn(token)

  if (expiresIn <= 0) {
    return () => {}
  }

  const timeoutDuration = Math.max(0, expiresIn - 5 * 60 * 1000)
  const timeoutId = setTimeout(onExpired, timeoutDuration)

  return () => clearTimeout(timeoutId)
}
```

### 4. Router Configuration Updates
Location: `src/router/index.tsx` (changes only)

```typescript
import { EmailLoginPage } from '@/pages/EmailLoginPage'
import { VerifyTokenPage } from '@/pages/VerifyTokenPage'

// In AppRouter component:
<Routes>
  {/* Fully public — no auth required */}
  <Route path="/login" element={<LoginPage />} />
  <Route path="/email-login" element={<EmailLoginPage />} />
  <Route path="/login/verify" element={<VerifyTokenPage />} />
  <Route path="/respond/:id" element={<RespondPage />} />
  
  {/* ... rest of routes ... */}
</Routes>
```

### 5. LoginPage Updates (Add Email Option)
Location: `src/pages/LoginPage.tsx` (add after Microsoft button)

```typescript
<div className="relative">
  <div className="absolute inset-0 flex items-center">
    <div className="w-full border-t border-muted" />
  </div>
  <div className="relative flex justify-center text-xs uppercase">
    <span className="bg-card px-2 text-muted-foreground">Or</span>
  </div>
</div>

<Button
  asChild
  variant="outline"
  className="w-full gap-2"
>
  <a href="/email-login">
    Sign in with Email
  </a>
</Button>
```

### 6. useAuth Hook - Key Additions
Location: `src/hooks/useAuth.ts`

```typescript
import { clearAuthStorage, setupTokenExpiryHandler } from '@/lib/auth'

// Add JWT auth state
const jwtToken = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null
const isJwtAuthenticated = !!jwtToken

// Update token getter to support JWT
setTokenGetter(async () => {
  if (msalAuthenticated && accounts.length > 0) {
    // ... MSAL token logic
  } else if (isJwtAuthenticated) {
    return jwtToken
  }
  return null
})

// Update logout to handle JWT
const logout = useCallback(() => {
  if (isJwtAuthenticated) {
    clearAuthStorage()
    window.location.href = '/login'
    return
  }
  // ... MSAL logout logic
}, [instance, isJwtAuthenticated])

// Add token expiry monitoring
useEffect(() => {
  if (!jwtToken) return
  const cleanup = setupTokenExpiryHandler(jwtToken, () => {
    clearAuthStorage()
    window.location.href = '/login'
  })
  return cleanup
}, [jwtToken])
```

## Integration Checklist

- [ ] Copy EmailLoginPage.tsx to src/pages/
- [ ] Copy VerifyTokenPage.tsx to src/pages/
- [ ] Copy auth.ts to src/lib/
- [ ] Update useAuth.ts with JWT support
- [ ] Update router with new routes
- [ ] Update LoginPage with email option
- [ ] Test email login flow
- [ ] Test token verification
- [ ] Test error states
- [ ] Test logout with JWT
- [ ] Verify localStorage usage
- [ ] Check CORS headers on backend
- [ ] Test redirect on token expiry

