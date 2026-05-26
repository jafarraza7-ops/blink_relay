import { useMemo, useState } from 'react'
import { Activity, CheckCircle2, Clock, FileText, Search, SlidersHorizontal, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { RequestTable } from '@/components/request/RequestTable'
import { useRequests } from '@/hooks/useRequests'
import { cn } from '@/lib/utils'
import {
  PODS, PRIORITIES, REQUEST_TYPES, REQUEST_STATUSES, STATUS_LABELS,
  STATUS_COLORS, POD_COLORS, PRIORITY_COLORS, TYPE_COLORS,
} from '@/lib/constants'
import type { Pod, RequestStatus, RequestType, Priority } from '@/lib/types'

const REFRESH_MS = 30_000

function toggle<T>(arr: T[], item: T): T[] {
  return arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item]
}

interface StatCardProps {
  icon: React.ElementType
  label: string
  value: number | undefined
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
          <p className="text-2xl font-bold leading-none">{value ?? '—'}</p>
          <p className="text-xs text-muted-foreground mt-1">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const [statuses, setStatuses] = useState<RequestStatus[]>([])
  const [pods, setPods] = useState<Pod[]>([])
  const [priorities, setPriorities] = useState<Priority[]>([])
  const [types, setTypes] = useState<RequestType[]>([])
  const [search, setSearch] = useState('')

  const { data, isLoading } = useRequests(
    { ...(search && { search }), page: 1, page_size: 500 },
    { refetchInterval: REFRESH_MS },
  )

  const { data: totalData }    = useRequests({ page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: newData }      = useRequests({ status: 'Submitted', page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: awaitData }    = useRequests({ status: 'AwaitingInfo', page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: approvedData } = useRequests({ status: 'Approved', page_size: 1 }, { refetchInterval: REFRESH_MS })

  const allItems = data?.items ?? []

  const filtered = useMemo(() => {
    let items = allItems
    if (statuses.length > 0)   items = items.filter((r) => statuses.includes(r.status))
    if (pods.length > 0)       items = items.filter((r) => pods.includes(r.pod))
    if (priorities.length > 0) items = items.filter((r) => priorities.includes(r.priority))
    if (types.length > 0)      items = items.filter((r) => types.includes(r.request_type))
    return items
  }, [allItems, statuses, pods, priorities, types])

  const activeCount = statuses.length + pods.length + priorities.length + types.length + (search ? 1 : 0)
  const hasFilters = activeCount > 0

  const clearAll = () => {
    setStatuses([])
    setPods([])
    setPriorities([])
    setTypes([])
    setSearch('')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Tech requests overview · refreshes every 30 s</p>
        </div>
        {hasFilters && (
          <Button variant="outline" size="sm" className="gap-1.5 text-xs h-8" onClick={clearAll}>
            <X className="h-3 w-3" />
            Clear {activeCount} filter{activeCount !== 1 ? 's' : ''}
          </Button>
        )}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={FileText}     label="Total"           value={totalData?.total}    color="bg-primary"    />
        <StatCard icon={Activity}     label="New / Submitted" value={newData?.total}      color="bg-amber-500"  />
        <StatCard icon={Clock}        label="Awaiting Info"   value={awaitData?.total}    color="bg-orange-500" />
        <StatCard icon={CheckCircle2} label="Approved"        value={approvedData?.total} color="bg-green-600"  />
      </div>

      {/* Filter bar */}
      <div className="space-y-3">
        {/* Search */}
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

        {/* Filter groups */}
        <div className="rounded-xl border bg-muted/30 divide-y">

          {/* Status */}
          <div className="px-4 py-3">
            <div className="flex items-center gap-2 mb-2.5">
              <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">Status</span>
              {statuses.length > 0 && (
                <span className="ml-auto text-xs text-primary font-medium cursor-pointer hover:underline"
                  onClick={() => setStatuses([])}>
                  Clear
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {REQUEST_STATUSES.map((s) => {
                const active = statuses.includes(s)
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStatuses((prev) => toggle(prev, s))}
                    className={cn(
                      'rounded-full px-3 py-1 text-xs font-medium border transition-all',
                      active ? STATUS_COLORS[s] : 'bg-background border-border hover:bg-muted'
                    )}
                    aria-pressed={active}
                  >
                    {STATUS_LABELS[s]}
                  </button>
                )
              })}
            </div>
          </div>

          {/* POD / Priority / Type — 3 columns */}
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x">

            <div className="px-4 py-3">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">POD</span>
                {pods.length > 0 && (
                  <span className="text-xs text-primary font-medium cursor-pointer hover:underline"
                    onClick={() => setPods([])}>
                    Clear
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {PODS.map((p) => {
                  const active = pods.includes(p)
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setPods((prev) => toggle(prev, p))}
                      className={cn(
                        'rounded-full px-3 py-1 text-xs font-medium border transition-all',
                        active ? POD_COLORS[p] : 'bg-background border-border hover:bg-muted'
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
                <span className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">Priority</span>
                {priorities.length > 0 && (
                  <span className="text-xs text-primary font-medium cursor-pointer hover:underline"
                    onClick={() => setPriorities([])}>
                    Clear
                  </span>
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
                        active ? PRIORITY_COLORS[p] : 'bg-background border-border hover:bg-muted'
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
                  <span className="text-xs text-primary font-medium cursor-pointer hover:underline"
                    onClick={() => setTypes([])}>
                    Clear
                  </span>
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
                        active ? TYPE_COLORS[t] : 'bg-background border-border hover:bg-muted'
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
      <div className="rounded-lg border bg-card">
        {hasFilters && !isLoading && (
          <div className="flex items-center justify-between px-4 pt-3 pb-1">
            <p className="text-xs text-muted-foreground">
              Showing <span className="font-semibold text-foreground">{filtered.length}</span> of {allItems.length} requests
            </p>
          </div>
        )}
        <RequestTable requests={filtered} isLoading={isLoading} />
      </div>
    </div>
  )
}
