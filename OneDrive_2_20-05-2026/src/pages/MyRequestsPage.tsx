import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  PlusCircle,
  Search,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { RequestTable } from '@/components/request/RequestTable'
import { useMyRequests } from '@/hooks/useRequests'
import { cn } from '@/lib/utils'
import { PRIORITIES, REQUEST_TYPES, STATUS_LABELS } from '@/lib/constants'
import type { BlinkRequest, Priority, RequestStatus, RequestType } from '@/lib/types'

const REFRESH_MS = 30_000

const STATUS_OPTIONS: RequestStatus[] = [
  'Submitted', 'InReview', 'AwaitingInfo', 'InfoReceived',
  'Approved', 'InProgress', 'Completed', 'Rejected',
]

const PENDING_STATUSES: RequestStatus[] = ['Submitted', 'InReview', 'AwaitingInfo', 'InfoReceived']

interface StatCardProps {
  icon: React.ElementType
  label: string
  value: number
  color: string
}

function StatCard({ icon: Icon, label, value, color }: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 pt-6 pb-5">
        <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-lg', color)}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-2xl font-bold leading-none">{value}</p>
          <p className="text-xs text-muted-foreground mt-1">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function toggle<T>(arr: T[], item: T): T[] {
  return arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item]
}

export function MyRequestsPage() {
  const [statuses, setStatuses] = useState<RequestStatus[]>([])
  const [priorities, setPriorities] = useState<Priority[]>([])
  const [types, setTypes] = useState<RequestType[]>([])
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  const { data, isLoading, isError } = useMyRequests(
    { page: 1, page_size: 500, search: search || undefined },
    { refetchInterval: REFRESH_MS },
  )

  const allItems: BlinkRequest[] = data?.items ?? []

  const stats = useMemo(() => {
    const counts = { total: allItems.length, pending: 0, awaitingInfo: 0, approved: 0, rejected: 0 }
    for (const r of allItems) {
      if (PENDING_STATUSES.includes(r.status)) counts.pending++
      if (r.status === 'AwaitingInfo') counts.awaitingInfo++
      if (['Approved', 'InProgress', 'Completed'].includes(r.status)) counts.approved++
      if (r.status === 'Rejected') counts.rejected++
    }
    return counts
  }, [allItems])

  const filtered = useMemo(() => {
    let items = allItems
    if (statuses.length > 0) items = items.filter((r) => statuses.includes(r.status))
    if (priorities.length > 0) items = items.filter((r) => priorities.includes(r.priority))
    if (types.length > 0) items = items.filter((r) => types.includes(r.request_type))
    return items
  }, [allItems, statuses, priorities, types])

  const hasFilters = statuses.length > 0 || priorities.length > 0 || types.length > 0 || search

  const clearAll = () => {
    setStatuses([])
    setPriorities([])
    setTypes([])
    setSearch('')
  }

  if (!isLoading && !isError && allItems.length === 0 && !search) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
          <FileText className="h-8 w-8 text-muted-foreground" />
        </div>
        <h2 className="text-xl font-semibold mb-1">No requests yet</h2>
        <p className="text-sm text-muted-foreground mb-6 max-w-sm">
          You haven't submitted any tech requests. Start one whenever you have a feature idea or
          have spotted a defect.
        </p>
        <Button asChild>
          <Link to="/submit">
            <PlusCircle className="mr-2 h-4 w-4" />
            Submit your first request
          </Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">My Requests</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track the status of every request you've submitted to the Blink product teams.
          </p>
        </div>
        <Button asChild>
          <Link to="/submit">
            <PlusCircle className="mr-2 h-4 w-4" />
            New Request
          </Link>
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={FileText}     label="Total submitted" value={stats.total}    color="bg-slate-600" />
        <StatCard icon={Clock}        label="Pending review"  value={stats.pending}  color="bg-amber-500" />
        <StatCard icon={CheckCircle2} label="Approved"        value={stats.approved} color="bg-green-600" />
        <StatCard icon={X}            label="Rejected"        value={stats.rejected} color="bg-red-500"   />
      </div>

      {/* Action-needed banner */}
      {stats.awaitingInfo > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-900">
                {stats.awaitingInfo === 1 ? '1 request needs' : `${stats.awaitingInfo} requests need`} additional information from you.
              </p>
              <p className="text-xs text-amber-800">
                Reviewers have asked clarifying questions — please respond so they can move forward.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const awaitingItems = allItems.filter((r) => r.status === 'AwaitingInfo')
                if (awaitingItems.length === 1) {
                  navigate(`/respond/${awaitingItems[0].id}`)
                } else {
                  setStatuses(['AwaitingInfo'])
                }
              }}
              className="border-amber-300 bg-white hover:bg-amber-100"
            >
              Review now
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="rounded-lg border bg-card p-4 space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">Filters</p>
          {hasFilters && (
            <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs" onClick={clearAll}>
              <X className="h-3 w-3" />
              Clear all
            </Button>
          )}
        </div>

        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by title…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">Status</p>
          <div className="flex flex-wrap gap-1.5">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setStatuses((prev) => toggle(prev, s))}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  statuses.includes(s)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-background hover:bg-muted border-border'
                )}
                aria-pressed={statuses.includes(s)}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">Priority</p>
          <div className="flex flex-wrap gap-1.5">
            {PRIORITIES.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPriorities((prev) => toggle(prev, p))}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  priorities.includes(p)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-background hover:bg-muted border-border'
                )}
                aria-pressed={priorities.includes(p)}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">Type</p>
          <div className="flex flex-wrap gap-1.5">
            {REQUEST_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTypes((prev) => toggle(prev, t))}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  types.includes(t)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-background hover:bg-muted border-border'
                )}
                aria-pressed={types.includes(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="pt-4">
          {hasFilters && !isLoading && (
            <p className="text-xs text-muted-foreground mb-3">
              {filtered.length} of {allItems.length} requests match active filters
            </p>
          )}
          <RequestTable
            requests={filtered}
            isLoading={isLoading}
            hideSubmitter
            rowLinkBuilder={(r) => `/respond/${r.id}`}
          />
          {isError && (
            <p className="text-sm text-destructive mt-2">
              Couldn't load your requests. Please refresh and try again.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
