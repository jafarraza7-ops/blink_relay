import { Link } from 'react-router-dom'
import { ArrowUpDown, ExternalLink } from 'lucide-react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { StatusBadge } from './StatusBadge'
import { PodBadge } from './PodBadge'
import { PriorityBadge } from './PriorityBadge'
import { TypeBadge } from './TypeBadge'
import { formatDate, truncate } from '@/lib/utils'
import type { BlinkRequest } from '@/lib/types'

interface RequestTableProps {
  requests: BlinkRequest[]
  isLoading?: boolean
  /** Build the row's title link target. Defaults to /requests/:id (reviewer view). */
  rowLinkBuilder?: (req: BlinkRequest) => string
  /** Hide the "Submitted by" column — useful when all rows share the same submitter. */
  hideSubmitter?: boolean
}

export function RequestTable({ requests, isLoading, rowLinkBuilder, hideSubmitter }: RequestTableProps) {
  const buildLink = rowLinkBuilder ?? ((req: BlinkRequest) => `/requests/${req.id}`)
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (requests.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <p className="text-lg font-medium">No requests found</p>
        <p className="text-sm">Try adjusting your filters</p>
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>
            <Button variant="ghost" size="sm" className="h-7 px-1 -ml-1">
              Reference <ArrowUpDown className="ml-1 h-3 w-3" />
            </Button>
          </TableHead>
          <TableHead>Title</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Pod</TableHead>
          <TableHead>Priority</TableHead>
          <TableHead>Status</TableHead>
          {!hideSubmitter && <TableHead>Submitted by</TableHead>}
          <TableHead>
            <Button variant="ghost" size="sm" className="h-7 px-1 -ml-1">
              Date <ArrowUpDown className="ml-1 h-3 w-3" />
            </Button>
          </TableHead>
          <TableHead>Service ticket</TableHead>
          <TableHead>Dev ticket</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {requests.map((req) => (
          <TableRow key={req.id}>
            <TableCell className="font-mono text-xs text-muted-foreground">
              {req.reference_id ?? '—'}
            </TableCell>
            <TableCell>
              <Link
                to={buildLink(req)}
                className="font-medium hover:text-primary transition-colors hover:underline"
              >
                {truncate(req.title, 60)}
              </Link>
            </TableCell>
            <TableCell><TypeBadge type={req.request_type} /></TableCell>
            <TableCell><PodBadge pod={req.pod} /></TableCell>
            <TableCell><PriorityBadge priority={req.priority} /></TableCell>
            <TableCell><StatusBadge status={req.status} /></TableCell>
            {!hideSubmitter && (
              <TableCell className="text-sm text-muted-foreground">
                {req.submitter_name}
              </TableCell>
            )}
            <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
              {formatDate(req.created_at)}
            </TableCell>
            <TableCell>
              {req.jsm_ticket_key ? (
                <a
                  href={req.jsm_ticket_url ?? '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  <ExternalLink className="h-3 w-3" />
                  {req.jsm_ticket_key}
                </a>
              ) : (
                <span className="text-xs text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell>
              {req.jira_ticket_key ? (
                <a
                  href={req.jira_ticket_url ?? '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  <ExternalLink className="h-3 w-3" />
                  {req.jira_ticket_key}
                </a>
              ) : (
                <span className="text-xs text-muted-foreground">—</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
