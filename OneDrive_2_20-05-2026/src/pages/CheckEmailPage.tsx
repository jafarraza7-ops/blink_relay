import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Mail, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import apiClient from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

export function CheckEmailPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { toast } = useToast()
  
  const email = location.state?.email || ''
  const [isResending, setIsResending] = useState(false)

  const handleResend = async () => {
    if (!email) {
      navigate('/auth/email/request')
      return
    }
    
    setIsResending(true)
    try {
      await apiClient.post('/auth/email/resend-token', { email })
      toast({
        title: 'Email sent',
        description: 'Check your inbox for a new login link'
      })
    } catch (err) {
      // Still show success message to prevent enumeration
      toast({
        title: 'Email sent',
        description: 'Check your inbox for a new login link'
      })
    } finally {
      setIsResending(false)
    }
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
        </div>

        {/* Content Card */}
        <Card className="shadow-lg border-0">
          <CardHeader>
            <div className="flex justify-center mb-4">
              <Mail className="h-12 w-12 text-blue-600" />
            </div>
            <CardTitle className="text-center">Check Your Email</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="text-center space-y-2">
              <p className="text-sm text-muted-foreground">
                We sent a login link to
              </p>
              <p className="font-semibold text-foreground break-all">
                {email || 'your email'}
              </p>
            </div>

            <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 space-y-2">
              <p><strong>✓ Click the link in the email</strong></p>
              <p className="text-xs">The link expires in 15 minutes</p>
            </div>

            <div className="space-y-3">
              <Button
                onClick={() => navigate('/auth/email/request')}
                variant="outline"
                className="w-full"
              >
                Try a different email
              </Button>
              <Button
                onClick={handleResend}
                disabled={isResending}
                className="w-full"
              >
                {isResending ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" />
                    Sending...
                  </>
                ) : (
                  'Resend email'
                )}
              </Button>
            </div>

            <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-900">
              <p><strong>Didn't get the email?</strong></p>
              <ul className="mt-2 space-y-1 text-amber-800">
                <li>• Check your spam or junk folder</li>
                <li>• Try a different email address</li>
                <li>• Make sure the email is spelled correctly</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        {/* Back Link */}
        <div className="text-center mt-6">
          <Button
            variant="ghost"
            onClick={() => navigate('/login')}
            className="gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to login
          </Button>
        </div>
      </div>
    </div>
  )
}
