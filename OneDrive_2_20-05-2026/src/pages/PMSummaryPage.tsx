import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { AlertTriangle, TrendingUp, Users, Clock, CheckCircle2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip as UITooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { useAuth } from '@/hooks/useAuth'
import apiClient from '@/lib/api'
import { useQuery } from '@tanstack/react-query'

interface SummaryData {
  total: number
  by_status: Record<string, number>
  cycle_time_avg_days: number
  requests_this_week: number
  requests_per_week: number
}

interface FunnelData {
  [key: string]: { count: number; conversion_percent: number }
}

interface PodPerformance {
  [key: string]: {
    total: number
    completed: number
    completion_percent: number
    in_progress: number
    awaiting_action: number
    cycle_time_days: number
    velocity_per_week: number
  }
}

interface Escalation {
  reference_id: string
  title: string
  status: string
  days_stuck: number
  last_updated: string
  submitter_email: string
}

interface EscalationData {
  total: number
  threshold_days: number
  escalations: Escalation[]
}

interface TrendData {
  [key: string]: number
}

const fetchSummary = async () => {
  const res = await apiClient.get('/analytics/summary')
  return res.data as SummaryData
}

const fetchFunnel = async () => {
  const res = await apiClient.get('/analytics/flow')
  return res.data as FunnelData
}

const fetchPodPerformance = async () => {
  const res = await apiClient.get('/analytics/pod-performance')
  return res.data as PodPerformance
}

const fetchEscalations = async () => {
  const res = await apiClient.get('/analytics/escalations')
  return res.data as EscalationData
}

const fetchTrend = async () => {
  const res = await apiClient.get('/analytics/trend')
  return res.data as TrendData
}

export function PMSummaryPage() {
  const navigate = useNavigate()
  const { isPM, isReviewer, isLoading: authLoading, user } = useAuth()

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!isPM && !isReviewer) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Access Denied</h1>
          <p className="text-muted-foreground">Only PMs and reviewers can view the summary dashboard</p>
        </div>
      </div>
    )
  }

  const authReady = !!user && (isPM || isReviewer)

  const { data: summary } = useQuery({ queryKey: ['analytics', 'summary'], queryFn: fetchSummary, refetchInterval: 30000, enabled: authReady })
  const { data: funnel } = useQuery({ queryKey: ['analytics', 'funnel'], queryFn: fetchFunnel, refetchInterval: 30000, enabled: authReady })
  const { data: podPerf } = useQuery({ queryKey: ['analytics', 'pod-performance'], queryFn: fetchPodPerformance, refetchInterval: 30000, enabled: authReady })
  const { data: escalations } = useQuery({ queryKey: ['analytics', 'escalations'], queryFn: fetchEscalations, refetchInterval: 30000, enabled: authReady })
  const { data: trend } = useQuery({ queryKey: ['analytics', 'trend'], queryFn: fetchTrend, refetchInterval: 30000, enabled: authReady })

  const funnelChartData = useMemo(() => {
    if (!funnel) return []
    return Object.entries(funnel).map(([status, data]) => ({
      name: status.replace(/_/g, ' ').toUpperCase(),
      count: data.count,
      conversion: data.conversion_percent,
    }))
  }, [funnel])

  const trendChartData = useMemo(() => {
    if (!trend) return []
    return Object.entries(trend).map(([week, count]) => ({
      week,
      requests: count as number,
    }))
  }, [trend])

  const drillInto = (filterType: string, filterValue: string) => {
    const params = new URLSearchParams()
    if (filterType === 'status') params.append('status', filterValue)
    if (filterType === 'pod') params.append('pod', filterValue)
    navigate(`/dashboard?${params.toString()}`)
  }

  const handleExport = () => {
    const timestamp = new Date().toISOString().split('T')[0]
    const csv = [
      ['PM Summary Dashboard Export', timestamp],
      [],
      ['OVERALL METRICS'],
      ['Total Requests', summary?.total || 0],
      ['Approved & Ready', summary?.by_status.approved || 0],
      ['Avg Cycle Time (days)', summary?.cycle_time_avg_days || 0],
      ['Requests This Week', summary?.requests_this_week || 0],
      [],
      ['REQUEST STATUS BREAKDOWN'],
      ...Object.entries(summary?.by_status || {}).map(([status, count]) => [status, count]),
      [],
      ['REQUEST FLOW FUNNEL'],
      ['Status', 'Count', 'Conversion %'],
      ...Object.entries(funnel || {}).map(([status, data]) => [status, data.count, data.conversion_percent]),
      [],
      ['POD PERFORMANCE'],
      ['Pod', 'Total', 'Completed', 'Completion %', 'In Progress', 'Cycle Time (days)', 'Velocity/Week'],
      ...Object.entries(podPerf || {}).map(([pod, perf]) => [
        pod,
        perf.total,
        perf.completed,
        perf.completion_percent,
        perf.in_progress,
        perf.cycle_time_days,
        perf.velocity_per_week,
      ]),
    ]
      .map(row => row.map(cell => `"${cell}"`).join(','))
      .join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `pm-dashboard-${timestamp}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">PM Summary Dashboard</h1>
          <p className="text-sm text-muted-foreground">Request health overview · updates every 30s</p>
        </div>
        <Button onClick={handleExport} variant="outline" size="sm" className="gap-1.5 text-xs h-8">
          📊 Export CSV
        </Button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <UITooltip>
          <TooltipTrigger asChild>
            <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/dashboard')}>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Requests</p>
                    <p className="text-3xl font-bold">{summary?.total ?? '—'}</p>
                  </div>
                  <Users className="h-8 w-8 text-blue-500" />
                </div>
              </CardContent>
            </Card>
          </TooltipTrigger>
          <TooltipContent>View all requests in dashboard</TooltipContent>
        </UITooltip>

        <UITooltip>
          <TooltipTrigger asChild>
            <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => drillInto('status', 'Approved')}>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Approved & Ready</p>
                    <p className="text-3xl font-bold">{summary?.by_status.approved ?? '—'}</p>
                    <p className="text-xs text-green-600 mt-1">Ready for development</p>
                  </div>
                  <CheckCircle2 className="h-8 w-8 text-green-500" />
                </div>
              </CardContent>
            </Card>
          </TooltipTrigger>
          <TooltipContent>Filter dashboard to approved requests</TooltipContent>
        </UITooltip>

        <UITooltip>
          <TooltipTrigger asChild>
            <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/dashboard')}>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Cycle Time</p>
                    <p className="text-3xl font-bold">{summary?.cycle_time_avg_days ?? '—'}</p>
                    <p className="text-xs text-muted-foreground mt-1">days to completion</p>
                  </div>
                  <Clock className="h-8 w-8 text-orange-500" />
                </div>
              </CardContent>
            </Card>
          </TooltipTrigger>
          <TooltipContent>View all requests in dashboard</TooltipContent>
        </UITooltip>

        <UITooltip>
          <TooltipTrigger asChild>
            <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/dashboard')}>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">This Week</p>
                    <p className="text-3xl font-bold">{summary?.requests_this_week ?? '—'}</p>
                    <p className="text-xs text-blue-600 mt-1">requests created</p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-blue-500" />
                </div>
              </CardContent>
            </Card>
          </TooltipTrigger>
          <TooltipContent>View all requests in dashboard</TooltipContent>
        </UITooltip>
      </div>

      {/* Funnel & Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Funnel Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Request Flow Funnel</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={funnelChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#3B82F6" name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Trend Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Weekly Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="requests" stroke="#3B82F6" strokeWidth={2} name="Requests Created" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Pod Performance */}
      <Card>
        <CardHeader>
          <CardTitle>Pod Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {podPerf && Object.entries(podPerf).map(([pod, perf]) => (
              perf.total > 0 && (
                <UITooltip key={pod}>
                  <TooltipTrigger asChild>
                    <div
                      className="border-l-4 border-blue-500 pl-4 py-2 cursor-pointer hover:bg-accent/50 transition-colors rounded"
                      onClick={() => drillInto('pod', pod)}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-semibold capitalize">{pod}</p>
                          <p className="text-sm text-muted-foreground">{perf.total} total requests</p>
                        </div>
                        <Badge variant={perf.completion_percent >= 50 ? 'default' : 'secondary'}>
                          {perf.completion_percent.toFixed(0)}% complete
                        </Badge>
                      </div>
                      <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                        <div>
                          <p className="text-muted-foreground">Cycle</p>
                          <p className="font-semibold">{perf.cycle_time_days}d</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">In Progress</p>
                          <p className="font-semibold">{perf.in_progress}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Velocity</p>
                          <p className="font-semibold">{perf.velocity_per_week}/wk</p>
                        </div>
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>Click to filter dashboard by {pod}</TooltipContent>
                </UITooltip>
              )
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Escalations */}
      {escalations && escalations.total > 0 && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5" />
                <div>
                  <CardTitle className="text-red-900">Escalations</CardTitle>
                  <p className="text-sm text-red-700">{escalations.total} requests stuck &gt;{escalations.threshold_days} days</p>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {escalations.escalations.slice(0, 5).map((esc, idx) => (
                <div key={idx} className="border-l-4 border-red-500 pl-3 py-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-semibold text-sm">{esc.reference_id}: {esc.title}</p>
                      <p className="text-xs text-muted-foreground">{esc.status} for {esc.days_stuck} days</p>
                    </div>
                    <Badge variant="destructive">{esc.days_stuck}d</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
