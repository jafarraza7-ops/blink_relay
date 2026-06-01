/**
 * useAuth.ts — Central authentication hook for Blink Relay.
 *
 * Supports both Azure AD/MSAL and email-based magic link authentication.
 * Prioritizes MSAL if available, falls back to email JWT from localStorage.
 *
 * Local dev bypass: set VITE_SKIP_AUTH=true in .env.local AND ensure the
 * backend also runs with SKIP_AUTH=true. Both flags must be set.
 */

import { useEffect, useState } from 'react'
import { useMsal, useIsAuthenticated } from '@azure/msal-react'
import { useQuery } from '@tanstack/react-query'
import { InteractionStatus } from '@azure/msal-browser'
import { authApi, setTokenGetter } from '@/lib/api'
import { loginRequest } from '@/lib/msalConfig'
import type { Role, User } from '@/lib/types'
import { PM_ROLES, REVIEWER_ROLES } from '@/lib/constants'

const SKIP_AUTH = import.meta.env.VITE_SKIP_AUTH === 'true'

export function useAuth() {
  const { instance, accounts, inProgress } = useMsal()
  const msalAuthenticated = useIsAuthenticated()
  const msalLoading = inProgress !== InteractionStatus.None
  
  const [emailUser, setEmailUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })

  // Check if user is authenticated via email JWT
  const emailToken = localStorage.getItem('auth_token')
  const isEmailAuthenticated = !!emailToken && !!emailUser

  // ── Token injection ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (SKIP_AUTH) {
      setTokenGetter(async () => 'dev-skip-auth-token')
      return
    }

    // Prioritize MSAL, fall back to email JWT
    setTokenGetter(async () => {
      // Try MSAL first
      const account = instance.getActiveAccount() ?? accounts[0]
      if (account) {
        try {
          const result = await instance.acquireTokenSilent({ ...loginRequest, account })
          return result.accessToken
        } catch {
          await instance.acquireTokenRedirect({ ...loginRequest, account })
          return null
        }
      }
      
      // Fall back to email JWT
      const token = localStorage.getItem('auth_token')
      if (token) return token
      
      return null
    })
  }, [instance, accounts])

  // ── /api/auth/me query ──────────────────────────────────────────────────────
  const shouldFetchMe = SKIP_AUTH ? true : (msalAuthenticated && !msalLoading) || isEmailAuthenticated
  
  const { data: user, isLoading: isLoadingUser } = useQuery<User>({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    enabled: shouldFetchMe,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  // ── Derived auth state ──────────────────────────────────────────────────────
  const isAuthenticated = SKIP_AUTH ? true : (msalAuthenticated || isEmailAuthenticated)
  const isLoading = SKIP_AUTH ? isLoadingUser : (msalLoading || (shouldFetchMe && isLoadingUser))
  const resolvedUser = user || emailUser

  const login = () => {
    if (!SKIP_AUTH) instance.loginRedirect(loginRequest)
  }

  const logout = () => {
    // Clear email auth
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user')
    setEmailUser(null)
    
    // Clear MSAL
    if (!SKIP_AUTH) instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin })
  }

  // ── Role helpers ────────────────────────────────────────────────────────────
  const hasRole = (...roles: Role[]): boolean =>
    resolvedUser?.roles.some((r) => roles.includes(r as Role)) ?? false

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
