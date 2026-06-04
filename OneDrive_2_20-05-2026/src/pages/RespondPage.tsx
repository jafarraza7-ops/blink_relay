import { useState } from 'react'
import { Link, useParams, Navigate } from 'react-router-dom'
import { AlertCircle, ArrowLeft, ExternalLink, Pencil, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { StatusBadge } from '@/components/request/StatusBadge'
import { PodBadge } from '@/components/request/PodBadge'
import { TypeBadge } from '@/components/request/TypeBadge'
import { PriorityBadge } from '@/components/request/PriorityBadge'
import { FileAttachment } from '@/components/request/FileAttachment'
import { EditRequestDialog } from '@/components/request/EditRequestDialog'
import { TruncatedBody, MessageThread } from '@/components/request/MessageThread'
import { useAuth } from '@/hooks/useAuth'
import { useRequest, useRespondToRequest, useCancelRequest } from '@/hooks/useRequests'
import { useThread } from '@/hooks/useThread'
import { useToast } from '@/components/ui/use-toast'
import { formatDate } from '@/lib/utils'
import type { RequestStatus } from '@/lib/types'

// Mirrors the backend EDITABLE_STATUSES set in app/api/requests.py
const EDITABLE_STATUSES: ReadonlySet<RequestStatus> = new Set<RequestStatus>([
  'Submitted',
  'InReview',
  'AwaitingInfo',
  'InfoReceived',
])

// Statuses from which a request can be cancelled
const CANCELLABLE_STATUSES: ReadonlySet<RequestStatus> = new Set<RequestStatus>([
  'Submitted',
  'InReview',
  'AwaitingInfo',
  'InfoReceived',
])

export function RespondPage() {
  const { id } = useParams<{ id: string }>()
  const { data: req, isLoading, isError } = useRequest(id ?? '')
  const { mutate: respond, isPending } = useRespondToRequest(id ?? '')
  const { mutate: cancel, isPending: isCancelling } = useCancelRequest(id ?? '')
  const { data: messages = [] } = useThread(id ?? '')
  const lastClarificationQ = [...messages].reverse().find((m) => m.message_type === 'clarification_question')
  const { toast } = useToast()
  const { isAuthenticated, user, isPM } = useAuth()
  const [responseText, setResponseText] = useState('')
  const [editOpen, setEditOpen] = useState(false)
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)

  if (!id) return <Navigate to="/" replace />

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (isError || !req) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-lg font-semibold">Request not found</p>
          <p className="text-sm text-muted-foreground mt-1">This link may be invalid or expired.</p>
        </div>
      </div>
    )
  }

  const isAwaitingInfo = req.status === 'AwaitingInfo'
  const isOwnRequest = isAuthenticated && user?.email === req.submitter_email
  const canEdit = (isOwnRequest || isPM) && EDITABLE_STATUSES.has(req.status)
  const canCancel = isOwnRequest && CANCELLABLE_STATUSES.has(req.status)
  // Authenticated users came in via /my-requests; anonymous users came from an
  // email link and shouldn't have a "back" target inside the app.
  const backTo = isAuthenticated ? '/my-requests' : null

  const handleRespond = () => {
    if (!responseText.trim()) return
    respond(
      { body: responseText.trim() },
      {
        onSuccess: () => {
          toast({ title: 'Response submitted', description: 'The review team has been notified.' })
          setResponseText('')
        },
        onError: (err) => toast({ title: 'Failed to submit', description: err.message, variant: 'destructive' }),
      }
    )
  }

  const handleCancel = () => {
    // Close dialog immediately (optimistic close)
    setShowCancelConfirm(false)

    cancel(undefined, {
      onSuccess: () => {
        toast({ title: 'Request cancelled', description: 'Your request has been cancelled successfully.' })
      },
      onError: (err) => {
        // Reopen dialog if cancellation fails
        setShowCancelConfirm(true)
        toast({ title: 'Failed to cancel', description: err.message, variant: 'destructive' })
      },
    })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 py-8">
      <div className="mx-auto max-w-2xl px-4 space-y-6">
        {/* Brand + back navigation */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-primary">
              <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4 text-primary-foreground" stroke="currentColor" strokeWidth={2}>
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <span className="font-semibold text-foreground">Blink Relay</span>
            <span className="text-muted-foreground">·</span>
            <span>Request Response</span>
          </div>

          {backTo && (
            <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
              <Link to={backTo}>
                <ArrowLeft className="h-4 w-4" />
                Back to my requests
              </Link>
            </Button>
          )}
        </div>

        {/* Request summary */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1 min-w-0">
                <CardTitle className="text-lg break-words">{req.title}</CardTitle>
                {req.reference_id && (
                  <p className="text-xs font-mono text-muted-foreground">{req.reference_id}</p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {canEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setEditOpen(true)}
                    className="gap-1.5"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit
                  </Button>
                )}
                {canCancel && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowCancelConfirm(true)}
                    className="gap-1.5 text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    Cancel Request
                  </Button>
                )}
                <StatusBadge status={req.status} />
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              <TypeBadge type={req.request_type} />
              <PodBadge pod={req.pod} />
              <PriorityBadge priority={req.priority} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Business Problem</p>
              <p className="mt-1 text-sm whitespace-pre-wrap">{req.business_problem}</p>
            </div>
            {req.expected_outcome && (
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Expected Outcome</p>
                <p className="mt-1 text-sm whitespace-pre-wrap">{req.expected_outcome}</p>
              </div>
            )}
            <div className="text-xs text-muted-foreground border-t pt-3">
              Submitted {formatDate(req.created_at)} by {req.submitter_name}
            </div>
          </CardContent>
        </Card>

        {/* Awaiting info — action required */}
        {isAwaitingInfo && (
          <Card className="border-amber-200 bg-amber-50">
            <CardHeader>
              <CardTitle className="text-base text-amber-800">Action Required</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {lastClarificationQ ? (
                <div className="rounded-md border border-blue-200 bg-blue-50 p-3">
                  <p className="text-xs font-medium text-blue-700 uppercase tracking-wide mb-1">Reviewer asked</p>
                  <div className="text-sm text-blue-900"><TruncatedBody text={lastClarificationQ.body} /></div>
                  <p className="text-xs text-blue-600 mt-1">— {lastClarificationQ.author_name}</p>
                </div>
              ) : (
                <p className="text-sm text-amber-700">
                  A reviewer has requested additional information. Please provide your response below.
                </p>
              )}
              <Textarea
                value={responseText}
                onChange={(e) => setResponseText(e.target.value)}
                placeholder="Provide the additional information requested…"
                rows={5}
                className="resize-none bg-white"
              />
              <Button
                onClick={handleRespond}
                disabled={!responseText.trim() || isPending}
                className="gap-2"
              >
                {isPending ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Submitting…
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Submit Response
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Jira ticket banner — shown when a ticket exists (Approved and beyond) */}
        {!isAwaitingInfo && req.jira_ticket_key && (
          <div className="rounded-lg border-2 border-blue-300 bg-blue-50 px-4 py-4 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">Jira Implementation Ticket</p>
            <a
              href={req.jira_ticket_url ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between rounded-md border border-blue-300 bg-white px-4 py-3 hover:bg-blue-50 transition-colors group"
            >
              <span className="text-xl font-bold text-blue-700 tracking-tight">{req.jira_ticket_key}</span>
              <ExternalLink className="h-5 w-5 text-blue-500 group-hover:text-blue-700" />
            </a>
            <p className="text-xs text-blue-700">Your request has been approved — click the ticket above to track implementation progress in Jira.</p>
          </div>
        )}

        {/* Status message for non-awaiting states */}
        {!isAwaitingInfo && !req.jira_ticket_key && (
          <div className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
            {req.status === 'InfoReceived'
              ? 'Your response has been received. The review team will follow up shortly.'
              : req.status === 'Approved'
              ? 'This request has been approved. A Jira ticket will be created shortly.'
              : req.status === 'Rejected'
              ? 'This request has been closed. Contact your PM if you have questions.'
              : 'No action is currently required. You will be notified of any updates by email.'}
          </div>
        )}

        {/* Conversation thread */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Conversation</CardTitle>
          </CardHeader>
          <CardContent>
            <MessageThread requestId={req.id} internalOnly={false} />
          </CardContent>
        </Card>

        {/* Attachments */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Attachments</CardTitle>
          </CardHeader>
          <CardContent>
            <FileAttachment requestId={req.id} canUpload={isAwaitingInfo} />
          </CardContent>
        </Card>
      </div>

      {/* Edit dialog — mounted only when the user is allowed to open it */}
      {canEdit && (
        <EditRequestDialog request={req} open={editOpen} onOpenChange={setEditOpen} />
      )}

      {/* Cancel confirmation dialog */}
      {showCancelConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-sm">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-100">
                  <AlertCircle className="h-5 w-5 text-red-600" />
                </div>
                <CardTitle className="text-red-900">Cancel Request?</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Are you sure you want to cancel this request? This action cannot be undone, and the review team will be notified.
              </p>
              <div className="flex gap-3 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setShowCancelConfirm(false)}
                  disabled={isCancelling}
                >
                  Keep Request
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleCancel}
                  disabled={isCancelling}
                >
                  {isCancelling ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" />
                      Cancelling…
                    </>
                  ) : (
                    'Cancel Request'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
