import { Link } from 'react-router-dom'
import { Calendar, ExternalLink } from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { StatusBadge } from './StatusBadge'
import { PodBadge } from './PodBadge'
import { PriorityBadge } from './PriorityBadge'
import { TypeBadge } from './TypeBadge'
import { formatDate, truncate } from '@/lib/utils'
import type { BlinkRequest } from '@/lib/types'

interface RequestCardProps {
  request: BlinkRequest
}

export function RequestCard({ request }: RequestCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <Link
              to={`/requests/${request.id}`}
              className="text-base font-semibold hover:text-primary transition-colors line-clamp-2"
            >
              {request.title}
            </Link>
            {request.reference_id && (
              <p className="text-xs text-muted-foreground mt-0.5">{request.reference_id}</p>
            )}
          </div>
          <StatusBadge status={request.status} className="shrink-0" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground line-clamp-2">
          {truncate(request.business_problem, 140)}
        </p>
        <div className="flex flex-wrap gap-1.5">
          <TypeBadge type={request.request_type} />
          <PodBadge pod={request.pod} />
          <PriorityBadge priority={request.priority} />
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            By {request.submitter_name}
          </span>
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {formatDate(request.created_at)}
          </div>
        </div>
        {request.jira_ticket_key && (
          <a
            href={request.jira_ticket_url ?? '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="h-3 w-3" />
            {request.jira_ticket_key}
          </a>
        )}
      </CardContent>
    </Card>
  )
}
