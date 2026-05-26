import { useMemo, useState } from 'react'
import { Activity, CheckCircle2, Clock, FileText, Search, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { RequestTable } from '@/components/request/RequestTable'
import { useRequests } from '@/hooks/useRequests'
import { cn } from '@/lib/utils'
import { PODS, PRIORITIES, REQUEST_TYPES, REQUEST_STATUSES, STATUS_LABELS } from '@/lib/constants'
import type { Pod, RequestStatus, RequestType, Priority } from '@/lib/types'

const REFRESH_MS = 30_000

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

function toggle<T>(arr: T[], item: T): T[] {
  return arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item]
}

interface PillGroupProps<T extends string> {
  label: string
  options: readonly T[]
  selected: T[]
  onToggle: (v: T) => void
  getLabel?: (v: T) => string
}

function PillGroup<T extends string>({ label, options, selected, onToggle, getLabel }: PillGroupProps<T>) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onToggle(opt)}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              selected.includes(opt)
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-background hover:bg-muted border-border'
            )}
            aria-pressed={selected.includes(opt)}
          >
            {getLabel ? getLabel(opt) : opt}
          </button>
        ))}
      </div>
    </div>
  )
}

export function DashboardPage() {
  const [statuses, setStatuses] = useState<RequestStatus[]>([])
  const [pods, setPods] = useState<Pod[]>([])
  const [priorities, setPriorities] = useState<Priority[]>([])
  const [types, setTypes] = useState<RequestType[]>([])
  const [search, setSearch] = useState('')

  // Fetch all requests — client-side handles multi-select filtering
  const { data, isLoading } = useRequests(
    { ...(search && { search }), page: 1, page_size: 500 },
    { refetchInterval: REFRESH_MS },
  )

  // Stat card queries — lightweight (page_size 1), auto-refresh
  const { data: totalData } = useRequests({ page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: newData } = useRequests({ status: 'Submitted', page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: awaitData } = useRequests({ status: 'AwaitingInfo', page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: approvedData } = useRequests({ status: 'Approved', page_size: 1 }, { refetchInterval: REFRESH_MS })

  const allItems = data?.items ?? []

  const filtered = useMemo(() => {
    let items = allItems
    if (statuses.length > 0) items = items.filter((r) => statuses.includes(r.status))
    if (pods.length > 0) items = items.filter((r) => pods.includes(r.pod))
    if (priorities.length > 0) items = items.filter((r) => priorities.includes(r.priority))
    if (types.length > 0) items = items.filter((r) => types.includes(r.request_type))
    return items
  }, [allItems, statuses, pods, priorities, types])

  const hasFilters = statuses.length > 0 || pods.length > 0 || priorities.length > 0 || types.length > 0 || search

  const clearAll = () => {
    setStatuses([])
    setPods([])
    setPriorities([])
    setTypes([])
    setSearch('')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Tech requests overview · refreshes every 30 s</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={FileText}    label="Total"          value={totalData?.total}    color="bg-primary"    />
        <StatCard icon={Activity}    label="New / Submitted" value={newData?.total}     color="bg-amber-500"  />
        <StatCard icon={Clock}       label="Awaiting Info"  value={awaitData?.total}    color="bg-orange-500" />
        <StatCard icon={CheckCircle2} label="Approved"      value={approvedData?.total} color="bg-green-600"  />
      </div>

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

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by title…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>

        <PillGroup
          label="Status"
          options={REQUEST_STATUSES}
          selected={statuses}
          onToggle={(v) => setStatuses((s) => toggle(s, v))}
          getLabel={(v) => STATUS_LABELS[v]}
        />

        <PillGroup
          label="POD"
          options={PODS}
          selected={pods}
          onToggle={(v) => setPods((s) => toggle(s, v))}
        />

        <PillGroup
          label="Priority"
          options={PRIORITIES}
          selected={priorities}
          onToggle={(v) => setPriorities((s) => toggle(s, v))}
        />

        <PillGroup
          label="Type"
          options={REQUEST_TYPES}
          selected={types}
          onToggle={(v) => setTypes((s) => toggle(s, v))}
        />
      </div>

      {/* Table */}
      <div className="rounded-lg border bg-card">
        {hasFilters && !isLoading && (
          <p className="px-4 pt-3 text-xs text-muted-foreground">
            {filtered.length} of {allItems.length} requests match active filters
          </p>
        )}
        <RequestTable requests={filtered} isLoading={isLoading} />
      </div>
    </div>
  )
}
