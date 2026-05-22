import { useEffect } from 'react'
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

  // Wire up the token getter for api.ts interceptor
  useEffect(() => {
    if (SKIP_AUTH) {
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
        await instance.acquireTokenRedirect({ ...loginRequest, account })
        return null
      }
    })
  }, [instance, accounts])

  const { data: user, isLoading: isLoadingUser } = useQuery<User>({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    // In skip-auth mode fetch from backend so SKIP_AUTH_AS role is respected
    enabled: SKIP_AUTH ? true : (msalAuthenticated && !msalLoading),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  const isAuthenticated = SKIP_AUTH ? true : msalAuthenticated
  const isLoading = SKIP_AUTH ? isLoadingUser : (msalLoading || (msalAuthenticated && isLoadingUser))
  const resolvedUser = user

  const login = () => { if (!SKIP_AUTH) instance.loginRedirect(loginRequest) }
  const logout = () => {
    if (!SKIP_AUTH) instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin })
  }

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
