/**
 * useAuth.ts — Central authentication hook for Blink Relay.
 *
 * Wraps Azure AD / MSAL authentication and the backend /api/auth/me profile
 * fetch into a single hook consumed by every page and route guard.
 *
 * Local dev bypass: set VITE_SKIP_AUTH=true in .env.local AND ensure the
 * backend also runs with SKIP_AUTH=true. Both flags must be set — frontend
 * alone won't work because the backend still validates the Bearer token.
 * The backend SKIP_AUTH_AS env var controls which role is impersonated.
 *
 * Exposes:
 *   isAuthenticated — true once MSAL confirms a session (or in skip-auth mode)
 *   isLoading       — true until MSAL interaction + /me fetch are both done
 *   user            — profile from /api/auth/me (roles, name, email)
 *   isReviewer      — PodReviewer | ProductManager | Admin
 *   isPM            — ProductManager | Admin
 *   hasRole         — ad-hoc role check for one-off gates
 *   login / logout  — MSAL redirect flows (no-ops in skip-auth mode)
 */

import { useEffect } from 'react'
import { useMsal, useIsAuthenticated } from '@azure/msal-react'
import { useQuery } from '@tanstack/react-query'
import { InteractionStatus } from '@azure/msal-browser'
import { authApi, setTokenGetter } from '@/lib/api'
import { loginRequest } from '@/lib/msalConfig'
import type { Role, User } from '@/lib/types'
import { PM_ROLES, REVIEWER_ROLES } from '@/lib/constants'

// ── Dev bypass flag ───────────────────────────────────────────────────────────
// Read once at module load — changing it at runtime requires a page reload.
const SKIP_AUTH = import.meta.env.VITE_SKIP_AUTH === 'true'

/** Provides auth state, user profile, and role-gating helpers. */
export function useAuth() {
  const { instance, accounts, inProgress } = useMsal()
  const msalAuthenticated = useIsAuthenticated()
  const msalLoading = inProgress !== InteractionStatus.None

  // ── Token injection ─────────────────────────────────────────────────────────
  // Register the getter with api.ts so every Axios request gets a fresh Bearer
  // token. Re-runs when accounts change (e.g. after redirect back from Azure).
  useEffect(() => {
    if (SKIP_AUTH) {
      // In skip-auth mode the backend accepts any non-empty token
      setTokenGetter(async () => 'dev-skip-auth-token')
      return
    }
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
  }, [instance, accounts])

  // ── /api/auth/me query ──────────────────────────────────────────────────────
  const { data: user, isLoading: isLoadingUser } = useQuery<User>({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    // In skip-auth mode fetch unconditionally so SKIP_AUTH_AS role is respected.
    // In normal mode wait until MSAL has a valid session before hitting the API.
    enabled: SKIP_AUTH ? true : (msalAuthenticated && !msalLoading),
    staleTime: 5 * 60 * 1000, // profile is stable; avoid hammering /me
    retry: false,
  })

  // ── Derived auth state ──────────────────────────────────────────────────────
  const isAuthenticated = SKIP_AUTH ? true : msalAuthenticated
  // In skip-auth mode the only loading state is the /me fetch.
  // In normal mode we're loading if MSAL is processing OR if /me is in-flight post-login.
  const isLoading = SKIP_AUTH ? isLoadingUser : (msalLoading || (msalAuthenticated && isLoadingUser))
  const resolvedUser = user

  const login = () => { if (!SKIP_AUTH) instance.loginRedirect(loginRequest) }
  const logout = () => {
    if (!SKIP_AUTH) instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin })
  }

  // ── Role helpers ────────────────────────────────────────────────────────────

  /** Returns true if the user has at least one of the given roles. */
  const hasRole = (...roles: Role[]): boolean =>
    resolvedUser?.roles.some((r) => roles.includes(r as Role)) ?? false

  // Pre-computed convenience booleans consumed throughout the UI for gating
  // reviewer-only actions (approve/reject/status change) and PM-only actions (export).
  const isReviewer = hasRole(...REVIEWER_ROLES)
  const isPM = hasRole(...PM_ROLES)

  return {
    isAuthenticated,
    isLoading,
    user: resolvedUser,
    login,
    logout,
    hasRole,
    isReviewer,
    isPM,
  }
}
