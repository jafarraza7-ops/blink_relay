/**
 * auth.ts — Auth utilities for JWT and token management.
 *
 * Provides helpers for:
 * - Getting/clearing JWT tokens from localStorage
 * - Decoding JWT claims (exp, iat) for token expiry checks
 * - Auto-logout on token expiry
 */

/** JWT token storage key */
const TOKEN_KEY = 'accessToken'
const USER_KEY = 'currentUser'

/**
 * Get the stored JWT token from localStorage.
 */
export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

/**
 * Clear JWT and user data from localStorage.
 * Called on logout or when token expires.
 */
export function clearAuthStorage(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    // localStorage may not be available in some contexts
  }
}

/**
 * Store JWT token and user data.
 */
export function storeAuth(token: string, user: { id: string; email: string; name: string }): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  } catch {
    // localStorage may not be available
  }
}

/**
 * Get stored user data.
 */
export function getStoredUser(): { id: string; email: string; name: string } | null {
  try {
    const userJson = localStorage.getItem(USER_KEY)
    return userJson ? JSON.parse(userJson) : null
  } catch {
    return null
  }
}

/**
 * Decode JWT claims without verification (client-side only).
 * WARNING: This does NOT verify the token signature. Use only to check expiry.
 */
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

/**
 * Check if JWT token is expired.
 * Returns true if token has no exp claim or exp is in the past.
 */
export function isTokenExpired(token: string): boolean {
  const claims = decodeJwt(token)
  if (!claims || typeof claims.exp !== 'number') {
    return false
  }
  // exp is in seconds; current time is in milliseconds
  return Date.now() >= claims.exp * 1000
}

/**
 * Get time until token expires in milliseconds.
 * Returns 0 if already expired, or negative if token has no exp claim.
 */
export function getTokenExpiresIn(token: string): number {
  const claims = decodeJwt(token)
  if (!claims || typeof claims.exp !== 'number') {
    return -1
  }
  const expiresAt = claims.exp * 1000
  return Math.max(0, expiresAt - Date.now())
}

/**
 * Set up auto-logout on token expiry.
 * Returns cleanup function to cancel the timeout.
 */
export function setupTokenExpiryHandler(token: string, onExpired: () => void): () => void {
  const expiresIn = getTokenExpiresIn(token)

  if (expiresIn <= 0) {
    // Token already expired or no exp claim
    return () => {}
  }

  // Set timeout to trigger 5 minutes before expiry, or immediately if less than 5 minutes
  const timeoutDuration = Math.max(0, expiresIn - 5 * 60 * 1000)
  const timeoutId = setTimeout(onExpired, timeoutDuration)

  return () => clearTimeout(timeoutId)
}
