import { Link, useParams, Navigate } from 'react-router-dom'
import { CheckCircle2, ClipboardCopy, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { StatusBadge } from '@/components/request/StatusBadge'
import { PodBadge } from '@/components/request/PodBadge'
import { TypeBadge } from '@/components/request/TypeBadge'
import { useRequest, useSimilarRequests } from '@/hooks/useRequests'
import { useToast } from '@/components/ui/use-toast'

export function ConfirmPage() {
  const { id } = useParams<{ id: string }>()
  const { data: req, isLoading, isError } = useRequest(id ?? '')
  const { data: similarRequests, isLoading: loadingSimilar } = useSimilarRequests(id ?? null)
  const { toast } = useToast()

  if (!id) return <Navigate to="/" replace />

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (isError || !req) {
    return <Navigate to="/" replace />
  }

  const copyRefId = () => {
    void navigator.clipboard.writeText(req.reference_id ?? req.id)
    toast({ title: 'Copied to clipboard' })
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      {/* Success header */}
      <div className="flex flex-col items-center gap-3 py-4 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
          <CheckCircle2 className="h-10 w-10 text-green-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Request submitted!</h1>
          <p className="text-muted-foreground mt-1">
            Your request has been received and will be reviewed shortly.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{req.title}</CardTitle>
          <CardDescription>
            <div className="flex flex-wrap gap-1.5 mt-1">
              <TypeBadge type={req.request_type} />
              <PodBadge pod={req.pod} />
              <StatusBadge status={req.status} />
            </div>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {req.reference_id && (
            <div className="flex items-center justify-between rounded-md bg-muted px-4 py-3">
              <div>
                <p className="text-xs text-muted-foreground">Reference ID</p>
                <p className="font-mono font-semibold">{req.reference_id}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={copyRefId} className="h-8 w-8">
                <ClipboardCopy className="h-4 w-4" />
              </Button>
            </div>
          )}

          <p className="text-sm text-muted-foreground">
            You&apos;ll receive email updates as your request progresses through the review workflow.
            If more information is needed, a reviewer will reach out directly.
          </p>
        </CardContent>
      </Card>

      {loadingSimilar && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Similar Tickets</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-16 rounded bg-muted animate-pulse" />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {!loadingSimilar && similarRequests && similarRequests.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Similar Tickets ({similarRequests.length})</CardTitle>
            <CardDescription>
              Review these existing requests — your issue may already be tracked
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {similarRequests.map((similar) => (
                <a
                  key={similar.id}
                  href={`/respond/${similar.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-lg border p-3 hover:bg-muted transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-primary hover:underline">
                        {similar.reference_id}
                      </p>
                      <p className="text-sm text-foreground line-clamp-2 mt-1">{similar.title}</p>
                      <div className="flex flex-wrap gap-1 mt-2">
                        <PodBadge pod={similar.pod} />
                        <StatusBadge status={similar.status} />
                      </div>
                    </div>
                    <div className="text-right whitespace-nowrap">
                      <p className="text-sm font-semibold text-green-600">
                        {similar.similarity_score.toFixed(0)}%
                      </p>
                      <p className="text-xs text-muted-foreground">match</p>
                    </div>
                  </div>
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex gap-3">
        <Button asChild variant="outline" className="flex-1">
          <Link to="/submit">Submit another request</Link>
        </Button>
        <Button asChild className="flex-1">
          <Link to={`/respond/${req.id}`}>
            <ExternalLink className="mr-2 h-4 w-4" />
            View request
          </Link>
        </Button>
      </div>
    </div>
  )
}
