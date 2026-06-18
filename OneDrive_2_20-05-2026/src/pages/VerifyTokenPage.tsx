import { useEffect, useRef, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { AlertCircle, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import apiClient from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

interface ErrorState {
  title: string
  message: string
  action?: string
}

export function VerifyTokenPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  
  const [state, setState] = useState<'loading' | 'success' | 'error'>('loading')
  const [error, setError] = useState<ErrorState | null>(null)
  const hasRun = useRef(false)

  const token = searchParams.get('token')

  useEffect(() => {
    if (hasRun.current) return
    hasRun.current = true

    const verifyToken = async () => {
      if (!token) {
        setError({
          title: 'Invalid Link',
          message: 'The login link is missing or invalid. Please request a new one.',
          action: 'Request New Link'
        })
        setState('error')
        return
      }

      try {
        // Call the verify endpoint
        const response = await apiClient.post('/auth/email/verify-token', { token })
        const { access_token, user } = response.data
        
        // Store JWT in localStorage
        localStorage.setItem('auth_token', access_token)
        localStorage.setItem('user', JSON.stringify(user))
        
        setState('success')
        
        // Redirect after brief delay
        setTimeout(() => {
          navigate('/my-requests')
        }, 1500)
      } catch (err: any) {
        const errorMessage = err.response?.data?.detail || err.message || 'Failed to log in'
        
        // Determine error type from message
        let title = 'Login Failed'
        let message = errorMessage
        
        if (errorMessage.includes('expired')) {
          title = 'Link Expired'
          message = 'Your login link has expired. Please request a new one.'
        } else if (errorMessage.includes('already')) {
          title = 'Link Already Used'
          message = 'This login link has already been used. Please request a new one.'
        }
        
        setError({
          title,
          message,
          action: 'Request New Link'
        })
        setState('error')
      }
    }

    verifyToken()
  }, [token, navigate])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary mx-auto mb-4">
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-primary-foreground" stroke="currentColor" strokeWidth={2}>
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-foreground">Blink Relay</h1>
        </div>

        {/* Content Card */}
        <Card className="shadow-lg border-0">
          {state === 'loading' && (
            <CardContent className="pt-8">
              <div className="text-center space-y-4">
                <div className="flex justify-center">
                  <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                </div>
                <p className="text-sm text-muted-foreground">Logging you in...</p>
                <p className="text-xs text-muted-foreground">Please don't close this page</p>
              </div>
            </CardContent>
          )}

          {state === 'success' && (
            <CardContent className="pt-8">
              <div className="text-center space-y-4">
                <CheckCircle className="h-12 w-12 text-green-600 mx-auto" />
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Welcome!</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    You're logged in. Redirecting to your dashboard...
                  </p>
                </div>
              </div>
            </CardContent>
          )}

          {state === 'error' && error && (
            <CardContent className="pt-8">
              <div className="text-center space-y-6">
                <AlertCircle className="h-12 w-12 text-red-600 mx-auto" />
                <div>
                  <h2 className="text-lg font-semibold text-foreground">{error.title}</h2>
                  <p className="text-sm text-muted-foreground mt-2">
                    {error.message}
                  </p>
                </div>
                
                <div className="space-y-3">
                  <Button
                    onClick={() => navigate('/auth/email/request')}
                    className="w-full"
                  >
                    {error.action || 'Request New Link'}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => navigate('/login')}
                    className="w-full"
                  >
                    Back to Login
                  </Button>
                </div>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Security Note */}
        <div className="text-center text-xs text-muted-foreground mt-6">
          <p>Your login link is secure and one-time use only</p>
        </div>
      </div>
    </div>
  )
}
