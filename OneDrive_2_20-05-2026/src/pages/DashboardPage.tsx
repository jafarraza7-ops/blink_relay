import { useState } from 'react'
import { Activity, CheckCircle2, Clock, FileText, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RequestTable } from '@/components/request/RequestTable'
import { useRequests } from '@/hooks/useRequests'
import { cn } from '@/lib/utils'
import { PODS, PRIORITIES, REQUEST_TYPES } from '@/lib/constants'
import type { Pod, RequestStatus, RequestType, Priority } from '@/lib/types'

const PAGE_SIZE = 50
const REFRESH_MS = 30_000

const STATUS_TABS: Array<{ value: RequestStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'Submitted', label: 'New' },
  { value: 'InReview', label: 'In Review' },
  { value: 'AwaitingInfo', label: 'Awaiting Info' },
  { value: 'InfoReceived', label: 'Info Received' },
  { value: 'Approved', label: 'Approved' },
  { value: 'Rejected', label: 'Rejected' },
  { value: 'InProgress', label: 'In Progress' },
  { value: 'Completed', label: 'Completed' },
]

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
  const [activeTab, setActiveTab] = useState<RequestStatus | 'all'>('all')
  const [search, setSearch] = useState('')
  const [pod, setPod] = useState<Pod | 'all'>('all')
  const [priority, setPriority] = useState<Priority | 'all'>('all')
  const [requestType, setRequestType] = useState<RequestType | 'all'>('all')
  const [page, setPage] = useState(1)

  const filters = {
    ...(activeTab !== 'all' && { status: activeTab }),
    ...(search && { search }),
    ...(pod !== 'all' && { pod }),
    ...(priority !== 'all' && { priority }),
    ...(requestType !== 'all' && { request_type: requestType }),
    page,
    page_size: PAGE_SIZE,
  }

  const { data, isLoading } = useRequests(filters, { refetchInterval: REFRESH_MS })

  // Stat card queries — lightweight (page_size 1), auto-refresh
  const { data: totalData } = useRequests({ page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: newData } = useRequests({ status: 'Submitted', page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: awaitData } = useRequests({ status: 'AwaitingInfo', page_size: 1 }, { refetchInterval: REFRESH_MS })
  const { data: approvedData } = useRequests({ status: 'Approved', page_size: 1 }, { refetchInterval: REFRESH_MS })

  const hasFilters = search || priority !== 'all' || requestType !== 'all'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Tech requests overview · refreshes every 30 s</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={FileText} label="Total" value={totalData?.total} color="bg-primary" />
        <StatCard icon={Activity} label="New / Submitted" value={newData?.total} color="bg-amber-500" />
        <StatCard icon={Clock} label="Awaiting Info" value={awaitData?.total} color="bg-orange-500" />
        <StatCard icon={CheckCircle2} label="Approved" value={approvedData?.total} color="bg-green-600" />
      </div>

      {/* POD filter pills */}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">Filter by POD</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => { setPod('all'); setPage(1) }}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              pod === 'all'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-background hover:bg-muted border-border'
            )}
          >
            All PODs
          </button>
          {PODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => { setPod(p); setPage(1) }}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                pod === p
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-background hover:bg-muted border-border'
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Status tabs */}
      <Tabs value={activeTab} onValueChange={(v) => { setActiveTab(v as RequestStatus | 'all'); setPage(1) }}>
        <TabsList className="flex-wrap h-auto gap-1 bg-muted/50">
          {STATUS_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value} className="text-xs">
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Search + type + priority row */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by title…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="pl-8"
          />
        </div>
        <Select value={requestType} onValueChange={(v) => { setRequestType(v as RequestType | 'all'); setPage(1) }}>
          <SelectTrigger className="w-[120px]"><SelectValue placeholder="All types" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {REQUEST_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={priority} onValueChange={(v) => { setPriority(v as Priority | 'all'); setPage(1) }}>
          <SelectTrigger className="w-[120px]"><SelectValue placeholder="Priority" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            {PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
          </SelectContent>
        </Select>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={() => { setSearch(''); setPriority('all'); setRequestType('all'); setPage(1) }}>
            Clear
          </Button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-lg border bg-card">
        <RequestTable requests={data?.items ?? []} isLoading={isLoading} />
      </div>

    </div>
  )
}
