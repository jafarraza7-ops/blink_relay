import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { StatusBadge } from './StatusBadge'
import { PodBadge } from './PodBadge'
import { PriorityBadge } from './PriorityBadge'
import { TypeBadge } from './TypeBadge'
import { formatDate, truncate } from '@/lib/utils'
import { PAGE_SIZE } from '@/lib/constants'
import type { BlinkRequest } from '@/lib/types'

export type SortCol = 'reference_id' | 'title' | 'request_type' | 'pod' | 'priority' | 'status' | 'created_at'
export type SortDir = 'asc' | 'desc'

const PRIORITY_ORDER: Record<string, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 }
const STATUS_ORDER: Record<string, number> = {
  Submitted: 0, InReview: 1, AwaitingInfo: 2, InfoReceived: 3,
  Approved: 4, InProgress: 5, Completed: 6, Rejected: 7, Closed: 8,
}

function sortRequests(requests: BlinkRequest[], col: SortCol, dir: SortDir): BlinkRequest[] {
  return [...requests].sort((a, b) => {
    let cmp = 0
    if (col === 'priority') {
      cmp = (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99)
    } else if (col === 'status') {
      cmp = (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99)
    } else if (col === 'created_at') {
      cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    } else {
      const av = (a[col] ?? '') as string
      const bv = (b[col] ?? '') as string
      cmp = av.localeCompare(bv)
    }
    return dir === 'asc' ? cmp : -cmp
  })
}

interface RequestTableProps {
  requests: BlinkRequest[]
  isLoading?: boolean
  /** Build the row's title link target. Defaults to /requests/:id (reviewer view). */
  rowLinkBuilder?: (req: BlinkRequest) => string
  /** Hide the "Submitted by" column — useful when all rows share the same submitter. */
  hideSubmitter?: boolean
}

function SortIcon({ col, active, dir }: { col: SortCol; active: SortCol; dir: SortDir }) {
  if (active !== col) return <ArrowUpDown className="ml-1 h-3 w-3 opacity-40" />
  return dir === 'asc'
    ? <ArrowUp className="ml-1 h-3 w-3 text-primary" />
    : <ArrowDown className="ml-1 h-3 w-3 text-primary" />
}

export function RequestTable({ requests, isLoading, rowLinkBuilder, hideSubmitter }: RequestTableProps) {
  const [sortCol, setSortCol] = useState<SortCol>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(1)
  const buildLink = rowLinkBuilder ?? ((req: BlinkRequest) => `/requests/${req.id}`)

  const sorted = useMemo(
    () => sortRequests(requests, sortCol, sortDir),
    [requests, sortCol, sortDir],
  )
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pageItems = useMemo(
    () => sorted.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [sorted, safePage],
  )

  const handleSort = (col: SortCol) => {
    if (col === sortCol) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
    setPage(1)
  }

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

  const SortBtn = ({ col, label }: { col: SortCol; label: string }) => (
    <Button
      variant="ghost"
      size="sm"
      className="h-7 px-1 -ml-1 font-medium"
      onClick={() => handleSort(col)}
    >
      {label}
      <SortIcon col={col} active={sortCol} dir={sortDir} />
    </Button>
  )

  return (
    <>
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead><SortBtn col="reference_id" label="Reference" /></TableHead>
          <TableHead><SortBtn col="title" label="Title" /></TableHead>
          <TableHead><SortBtn col="request_type" label="Type" /></TableHead>
          <TableHead><SortBtn col="pod" label="Pod" /></TableHead>
          <TableHead><SortBtn col="priority" label="Priority" /></TableHead>
          <TableHead><SortBtn col="status" label="Status" /></TableHead>
          {!hideSubmitter && <TableHead>Submitted by</TableHead>}
          <TableHead><SortBtn col="created_at" label="Date" /></TableHead>
          <TableHead>Service ticket</TableHead>
          <TableHead>Dev ticket</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {pageItems.map((req) => (
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

    {totalPages > 1 && (
      <div className="flex items-center justify-between border-t px-4 py-3">
        <p className="text-xs text-muted-foreground">
          Showing {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, sorted.length)} of {sorted.length}
        </p>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            className="h-7 w-7 p-0"
            disabled={safePage <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <Button
              key={p}
              variant={p === safePage ? 'default' : 'outline'}
              size="sm"
              className="h-7 w-7 p-0 text-xs"
              onClick={() => setPage(p)}
            >
              {p}
            </Button>
          ))}
          <Button
            variant="outline"
            size="sm"
            className="h-7 w-7 p-0"
            disabled={safePage >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )}
  </>
  )
}
