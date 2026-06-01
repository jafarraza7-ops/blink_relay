import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Mail, ArrowRight, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import apiClient from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

export function EmailLoginPage() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { toast } = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    if (!email.trim()) {
      setError('Please enter your email')
      return
    }

    setIsLoading(true)
    try {
      await apiClient.post('/auth/email/request-login', { email })
      setSubmitted(true)
      // Redirect to check-email page after brief delay
      setTimeout(() => {
        navigate('/auth/email/check-email', { state: { email } })
      }, 800)
    } catch (err) {
      // Even on error, show the check-email screen to prevent enumeration
      setSubmitted(true)
      setTimeout(() => {
        navigate('/auth/email/check-email', { state: { email } })
      }, 800)
    } finally {
      setIsLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50 px-4">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto" />
          <p className="text-sm text-muted-foreground mt-4">Redirecting...</p>
        </div>
      </div>
    )
  }

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
          <p className="text-sm text-muted-foreground mt-2">Product Intake System</p>
        </div>

        {/* Login Card */}
        <Card className="shadow-lg border-0">
          <CardHeader>
            <CardTitle className="text-center">Log in with Email</CardTitle>
            <p className="text-sm text-muted-foreground text-center mt-2">
              We'll send you a secure link to log in
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium">
                  Email Address
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="your.email@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                  autoFocus
                  className="h-10"
                />
              </div>

              <Button
                type="submit"
                disabled={isLoading || !email.trim()}
                className="w-full gap-2 h-10"
              >
                {isLoading ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Mail className="h-4 w-4" />
                    Send Login Link
                  </>
                )}
              </Button>

              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-muted-foreground/20"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="bg-white px-2 text-muted-foreground">Or</span>
                </div>
              </div>

              <Button
                type="button"
                variant="outline"
                className="w-full gap-2 h-10"
                onClick={() => navigate('/login')}
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 6v6l4 2" />
                </svg>
                Continue with Microsoft
              </Button>
            </form>

            {/* Security Info */}
            <div className="mt-6 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
              <p className="text-xs text-blue-900">
                <strong>🔒 Secure & Private:</strong> We'll never ask for your password. 
                Check your email and click the secure link we send you.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="text-center text-sm text-muted-foreground mt-6">
          <p>Need help? <Link to="/contact" className="text-primary hover:underline">Contact support</Link></p>
        </div>
      </div>
    </div>
  )
}
