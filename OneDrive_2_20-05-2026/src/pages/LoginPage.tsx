import { useEffect } from 'react'
import { Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'

export function LoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth()

  // If already authenticated (e.g. user navigated directly to /login), redirect is handled by router
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      void login()
    }
  }, [isAuthenticated, isLoading, login])

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
          <div>
            <h2 className="text-lg font-semibold">Sign in to continue</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Use your Blink Network Microsoft account
            </p>
          </div>

          <Button
            onClick={() => void login()}
            className="w-full gap-2"
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Redirecting…
              </span>
            ) : (
              <>
                <MicrosoftIcon />
                Sign in with Microsoft
              </>
            )}
          </Button>

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
            <a href="/auth/email/request">
              Sign in with Email
            </a>
          </Button>
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

function MicrosoftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  )
}
