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
import { PRIORITIES, REQUEST_TYPES, STATUS_LABELS, STATUS_COLORS, PRIORITY_COLORS, TYPE_COLORS } from '@/lib/constants'
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

  const activeCount = statuses.length + priorities.length + types.length + (search ? 1 : 0)
  const hasFilters = activeCount > 0

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
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">My Requests</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track the status of every request you've submitted to the Blink product teams.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasFilters && (
            <Button variant="outline" size="sm" className="gap-1.5 text-xs h-8" onClick={clearAll}>
              <X className="h-3 w-3" />
              Clear {activeCount} filter{activeCount !== 1 ? 's' : ''}
            </Button>
          )}
          <Button asChild>
            <Link to="/submit">
              <PlusCircle className="mr-2 h-4 w-4" />
              New Request
            </Link>
          </Button>
        </div>
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

      {/* Filter bar */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search requests by title…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-9 h-10"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="rounded-xl border bg-muted/30 divide-y">
          {/* Status */}
          <div className="px-4 py-3">
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">Status</span>
              {statuses.length > 0 && (
                <span className="text-xs text-primary font-medium cursor-pointer hover:underline" onClick={() => setStatuses([])}>Clear</span>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {STATUS_OPTIONS.map((s) => {
                const active = statuses.includes(s)
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStatuses((prev) => toggle(prev, s))}
                    className={cn(
                      'rounded-full px-3 py-1 text-xs font-medium border transition-all',
                      cn(STATUS_COLORS[s], active ? 'shadow-sm' : 'opacity-40 hover:opacity-75')
                    )}
                    aria-pressed={active}
                  >
                    {STATUS_LABELS[s]}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Priority + Type */}
          <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x">
            <div className="px-4 py-3">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">Priority</span>
                {priorities.length > 0 && (
                  <span className="text-xs text-primary font-medium cursor-pointer hover:underline" onClick={() => setPriorities([])}>Clear</span>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {PRIORITIES.map((p) => {
                  const active = priorities.includes(p)
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setPriorities((prev) => toggle(prev, p))}
                      className={cn(
                        'rounded-full px-3 py-1 text-xs font-medium border transition-all',
                        cn(PRIORITY_COLORS[p], active ? 'shadow-sm' : 'opacity-40 hover:opacity-75')
                      )}
                      aria-pressed={active}
                    >
                      {p}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="px-4 py-3">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">Type</span>
                {types.length > 0 && (
                  <span className="text-xs text-primary font-medium cursor-pointer hover:underline" onClick={() => setTypes([])}>Clear</span>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {REQUEST_TYPES.map((t) => {
                  const active = types.includes(t)
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setTypes((prev) => toggle(prev, t))}
                      className={cn(
                        'rounded-full px-3 py-1 text-xs font-medium border transition-all',
                        cn(TYPE_COLORS[t], active ? 'shadow-sm' : 'opacity-40 hover:opacity-75')
                      )}
                      aria-pressed={active}
                    >
                      {t}
                    </button>
                  )
                })}
              </div>
            </div>
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
