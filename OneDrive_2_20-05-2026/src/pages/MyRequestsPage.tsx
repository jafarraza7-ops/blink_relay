import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  PlusCircle,
  Search,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RequestTable } from '@/components/request/RequestTable'
import { useMyRequests } from '@/hooks/useRequests'
import { cn } from '@/lib/utils'
import type { BlinkRequest, RequestStatus } from '@/lib/types'

const PAGE_SIZE = 25
const REFRESH_MS = 30_000

const STATUS_TABS: Array<{ value: RequestStatus | 'all' | 'pending'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'AwaitingInfo', label: 'Action needed' },
  { value: 'Approved', label: 'Approved' },
  { value: 'InProgress', label: 'In Progress' },
  { value: 'Completed', label: 'Completed' },
  { value: 'Rejected', label: 'Rejected' },
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

export function MyRequestsPage() {
  const [activeTab, setActiveTab] = useState<RequestStatus | 'all' | 'pending'>('all')
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  // Fetch a wide page (no status filter) so the stat cards reflect the user's full state.
  // Filtering by status is then done client-side based on the active tab.
  const { data, isLoading, isError } = useMyRequests(
    { page: 1, page_size: 100, search: search || undefined },
    { refetchInterval: REFRESH_MS },
  )

  const allItems: BlinkRequest[] = data?.items ?? []

  const stats = useMemo(() => {
    const counts = {
      total: allItems.length,
      pending: 0,
      awaitingInfo: 0,
      approved: 0,
      rejected: 0,
    }
    for (const r of allItems) {
      if (PENDING_STATUSES.includes(r.status)) counts.pending++
      if (r.status === 'AwaitingInfo') counts.awaitingInfo++
      if (r.status === 'Approved' || r.status === 'InProgress' || r.status === 'Completed') counts.approved++
      if (r.status === 'Rejected') counts.rejected++
    }
    return counts
  }, [allItems])

  const visibleItems = useMemo(() => {
    if (activeTab === 'all') return allItems
    if (activeTab === 'pending') return allItems.filter((r) => PENDING_STATUSES.includes(r.status))
    return allItems.filter((r) => r.status === activeTab)
  }, [allItems, activeTab])

  const pageItems = visibleItems.slice(0, PAGE_SIZE)

  // ── Empty state — user has never submitted a request ────────────────────────
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
      {/* ── Header ─────────────────────────────────────────────────────────── */}
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

      {/* ── Stats ──────────────────────────────────────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={FileText}      label="Total submitted"  value={stats.total}        color="bg-slate-600"  />
        <StatCard icon={Clock}         label="Pending review"   value={stats.pending}      color="bg-amber-500"  />
        <StatCard icon={CheckCircle2}  label="Approved"         value={stats.approved}     color="bg-green-600"  />
        <StatCard icon={XCircle}       label="Rejected"         value={stats.rejected}     color="bg-red-500"    />
      </div>

      {/* ── Action-needed banner ───────────────────────────────────────────── */}
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
                  setActiveTab('AwaitingInfo')
                }
              }}
              className="border-amber-300 bg-white hover:bg-amber-100"
            >
              Review now
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── Filter bar ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
          <TabsList className="flex-wrap">
            {STATUS_TABS.map(({ value, label }) => (
              <TabsTrigger key={value} value={value}>
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by title…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* ── Table ──────────────────────────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-6">
          <RequestTable
            requests={pageItems}
            isLoading={isLoading}
            hideSubmitter
            rowLinkBuilder={(r) => `/respond/${r.id}`}
          />
          {!isLoading && visibleItems.length > PAGE_SIZE && (
            <p className="text-xs text-muted-foreground mt-3 text-center">
              Showing {PAGE_SIZE} of {visibleItems.length} — refine filters to narrow down.
            </p>
          )}
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
