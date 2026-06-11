import { type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { SubmitPage } from '@/pages/SubmitPage'
import { ConfirmPage } from '@/pages/ConfirmPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { PMSummaryPage } from '@/pages/PMSummaryPage'
import { MyRequestsPage } from '@/pages/MyRequestsPage'
import { ReviewPage } from '@/pages/ReviewPage'
import { EmailLoginPage } from "@/pages/EmailLoginPage"
import { VerifyTokenPage } from "@/pages/VerifyTokenPage"
import { CheckEmailPage } from "@/pages/CheckEmailPage"
import { RespondPage } from '@/pages/RespondPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

function LoadingScreen() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, login } = useAuth()
  const location = useLocation()

  if (isLoading) return <LoadingScreen />

  if (!isAuthenticated) {
    void login()
    return <LoginPage />
  }

  void location
  return <>{children}</>
}

function RequireReviewer({ children }: { children: ReactNode }) {
  const { isReviewer, isLoading } = useAuth()
  if (isLoading) return <LoadingScreen />
  if (!isReviewer) return <Navigate to="/my-requests" replace />
  return <>{children}</>
}

function SmartRedirect() {
  const { isPM, isLoading } = useAuth()
  if (isLoading) return <LoadingScreen />
  return <Navigate to={isPM ? '/dashboard' : '/my-requests'} replace />
}

export function AppRouter() {
  return (
    <Routes>
      {/* Fully public — no auth required */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/email/request" element={<EmailLoginPage />} />
      <Route path="/auth/email/callback" element={<VerifyTokenPage />} />
      <Route path="/auth/email/check-email" element={<CheckEmailPage />} />
      <Route path="/respond/:id" element={<RespondPage />} />

      {/* Authenticated — wrapped in AppShell */}
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<SmartRedirect />} />
        <Route path="submit" element={<SubmitPage />} />
        <Route path="confirm/:id" element={<ConfirmPage />} />
        <Route path="my-requests" element={<MyRequestsPage />} />

        <Route
          path="dashboard"
          element={
            <RequireReviewer>
              <DashboardPage />
            </RequireReviewer>
          }
        />
        <Route
          path="pm-summary"
          element={
            <RequireReviewer>
              <PMSummaryPage />
            </RequireReviewer>
          }
        />
        <Route
          path="requests/:id"
          element={
            <RequireReviewer>
              <ReviewPage />
            </RequireReviewer>
          }
        />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
