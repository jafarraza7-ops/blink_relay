import { useState } from 'react'
import { useParams, Navigate, Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, ExternalLink, MessageSquare, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { StatusBadge } from '@/components/request/StatusBadge'
import { PodBadge } from '@/components/request/PodBadge'
import { PriorityBadge } from '@/components/request/PriorityBadge'
import { TypeBadge } from '@/components/request/TypeBadge'
import { MessageThread } from '@/components/request/MessageThread'
import { FileAttachment } from '@/components/request/FileAttachment'
import { useRequest, useApproveRequest, useRejectRequest, useUpdateStatus, useSendClarification } from '@/hooks/useRequests'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/components/ui/use-toast'
import { formatDateTime } from '@/lib/utils'
import { REQUEST_STATUSES, STATUS_LABELS, REGION_LABELS } from '@/lib/constants'
import type { RequestStatus } from '@/lib/types'

const REJECTION_REASONS = [
  'Out of scope',
  'Duplicate request',
  'Insufficient information',
  'Not prioritised this cycle',
  'Alternative solution exists',
  'Other',
]

export function ReviewPage() {
  const { id } = useParams<{ id: string }>()
  const { data: req, isLoading, isError } = useRequest(id ?? '')
  const { isPM } = useAuth()
  const { toast } = useToast()

  const approve = useApproveRequest(id ?? '')
  const reject = useRejectRequest(id ?? '')
  const updateStatus = useUpdateStatus(id ?? '')

  const [rejectReason, setRejectReason] = useState('')
  const [rejectComment, setRejectComment] = useState('')
  const [newStatus, setNewStatus] = useState<RequestStatus | ''>('')
  const [clarifyText, setClarifyText] = useState('')

  const clarify = useSendClarification(id ?? '')

  if (!id) return <Navigate to="/dashboard" replace />

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (isError || !req) return <Navigate to="/dashboard" replace />

  const handleApprove = () => {
    approve.mutate({}, {
      onSuccess: () => toast({ title: 'Request approved', description: 'Jira ticket creation queued.' }),
      onError: (err) => toast({ title: 'Failed to approve', description: err.message, variant: 'destructive' }),
    })
  }

  const handleReject = () => {
    if (!rejectReason) return
    reject.mutate({ reason: rejectReason, comment: rejectComment || undefined }, {
      onSuccess: () => toast({ title: 'Request rejected' }),
      onError: (err) => toast({ title: 'Failed to reject', description: err.message, variant: 'destructive' }),
    })
  }

  const handleStatusChange = () => {
    if (!newStatus) return
    updateStatus.mutate({ status: newStatus }, {
      onSuccess: () => { toast({ title: `Status updated to ${STATUS_LABELS[newStatus]}` }); setNewStatus('') },
      onError: (err) => toast({ title: 'Failed to update status', description: err.message, variant: 'destructive' }),
    })
  }

  const handleClarify = () => {
    if (!clarifyText.trim()) return
    clarify.mutate({ body: clarifyText.trim() }, {
      onSuccess: () => { toast({ title: 'Clarification sent', description: 'Requestor has been notified by email.' }); setClarifyText('') },
      onError: (err) => toast({ title: 'Failed to send', description: err.message, variant: 'destructive' }),
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Button asChild variant="ghost" size="sm">
          <Link to="/dashboard"><ArrowLeft className="mr-1 h-4 w-4" />Dashboard</Link>
        </Button>
      </div>

      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold">{req.title}</h1>
          {req.reference_id && <p className="font-mono text-sm text-muted-foreground">{req.reference_id}</p>}
        </div>
        <StatusBadge status={req.status} className="shrink-0 text-sm px-3 py-1" />
      </div>

      <div className="flex flex-wrap gap-2">
        <TypeBadge type={req.request_type} />
        <PodBadge pod={req.pod} />
        <PriorityBadge priority={req.priority} />
        {req.jira_ticket_key && (
          <a href={req.jira_ticket_url ?? '#'} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 hover:bg-blue-100">
            <ExternalLink className="h-3 w-3" />{req.jira_ticket_key}
          </a>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content */}
        <div className="space-y-6 lg:col-span-2">
          {/* Details */}
          <Card>
            <CardHeader><CardTitle className="text-base">Request Details</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Field label="Business Problem" value={req.business_problem} />
              <Field label="Region" value={REGION_LABELS[req.region]} />
              {req.expected_outcome && <Field label="Expected Outcome" value={req.expected_outcome} />}
              {req.steps_to_reproduce && <Field label="Steps to Reproduce" value={req.steps_to_reproduce} />}
              <Field label="Affected Area" value={req.affected_area} />
              {req.additional_context && <Field label="Additional Context" value={req.additional_context} />}
              <div className="flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
                <span>Submitted by {req.submitter_name} ({req.submitter_email})</span>
                <span>{formatDateTime(req.created_at)}</span>
              </div>
            </CardContent>
          </Card>

          {/* Thread */}
          <Card>
            <CardHeader><CardTitle className="text-base">Conversation</CardTitle></CardHeader>
            <CardContent><MessageThread requestId={req.id} internalOnly /></CardContent>
          </Card>

          {/* Files */}
          <Card>
            <CardHeader><CardTitle className="text-base">Attachments</CardTitle></CardHeader>
            <CardContent><FileAttachment requestId={req.id} /></CardContent>
          </Card>
        </div>

        {/* Actions sidebar */}
        {isPM && (
          <div className="space-y-4">
            {/* Approve */}
            {!['Approved', 'Rejected', 'Completed', 'Closed'].includes(req.status) && (
              <Card>
                <CardHeader><CardTitle className="text-base text-green-700">Approve</CardTitle></CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-3">Approving will create a Jira ticket automatically.</p>
                  <Button className="w-full bg-green-600 hover:bg-green-700 gap-2" onClick={handleApprove} disabled={approve.isPending}>
                    <CheckCircle2 className="h-4 w-4" />
                    {approve.isPending ? 'Approving…' : 'Approve Request'}
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Reject */}
            {!['Rejected', 'Completed', 'Closed'].includes(req.status) && (
              <Card>
                <CardHeader><CardTitle className="text-base text-destructive">Reject</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <Select value={rejectReason} onValueChange={setRejectReason}>
                    <SelectTrigger><SelectValue placeholder="Select reason" /></SelectTrigger>
                    <SelectContent>
                      {REJECTION_REASONS.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Textarea
                    placeholder="Optional comment for requestor…"
                    value={rejectComment}
                    onChange={(e) => setRejectComment(e.target.value)}
                    rows={3}
                    className="resize-none"
                  />
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="destructive" className="w-full gap-2" disabled={!rejectReason}>
                        <XCircle className="h-4 w-4" />Reject Request
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Reject this request?</AlertDialogTitle>
                        <AlertDialogDescription>
                          Reason: <strong>{rejectReason}</strong>. The requestor will be notified by email.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleReject} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                          Confirm Rejection
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </CardContent>
              </Card>
            )}

            {/* Status change */}
            <Card>
              <CardHeader><CardTitle className="text-base">Update Status</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <Select value={newStatus} onValueChange={(v) => setNewStatus(v as RequestStatus)}>
                  <SelectTrigger><SelectValue placeholder="Select status" /></SelectTrigger>
                  <SelectContent>
                    {REQUEST_STATUSES.filter((s) => s !== req.status).map((s) => (
                      <SelectItem key={s} value={s}>{STATUS_LABELS[s]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" className="w-full" onClick={handleStatusChange} disabled={!newStatus || updateStatus.isPending}>
                  {updateStatus.isPending ? 'Updating…' : 'Update Status'}
                </Button>
              </CardContent>
            </Card>

            {/* Request clarification */}
            {!['Approved', 'Rejected', 'Completed', 'Closed'].includes(req.status) && (
              <Card>
                <CardHeader><CardTitle className="text-base text-amber-700">Request Clarification</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-muted-foreground">Ask the requestor for more details. They will receive an email with a link to respond.</p>
                  <Textarea
                    placeholder="What additional information do you need?"
                    value={clarifyText}
                    onChange={(e) => setClarifyText(e.target.value)}
                    rows={3}
                    className="resize-none"
                  />
                  <Button variant="outline" className="w-full gap-2" onClick={handleClarify} disabled={!clarifyText.trim() || clarify.isPending}>
                    <MessageSquare className="h-4 w-4" />
                    {clarify.isPending ? 'Sending…' : 'Send to Requestor'}
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm whitespace-pre-wrap">{value}</p>
    </div>
  )
}
