import { useMemo } from 'react'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { AlertTriangle, TrendingUp, Users, Clock, CheckCircle2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '@/hooks/useAuth'
import axios from 'axios'
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
  const res = await axios.get('/api/analytics/summary')
  return res.data as SummaryData
}

const fetchFunnel = async () => {
  const res = await axios.get('/api/analytics/flow')
  return res.data as FunnelData
}

const fetchPodPerformance = async () => {
  const res = await axios.get('/api/analytics/pod-performance')
  return res.data as PodPerformance
}

const fetchEscalations = async () => {
  const res = await axios.get('/api/analytics/escalations')
  return res.data as EscalationData
}

const fetchTrend = async () => {
  const res = await axios.get('/api/analytics/trend')
  return res.data as TrendData
}

export function PMSummaryPage() {
  const { isPM, isReviewer } = useAuth()

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

  const { data: summary } = useQuery({ queryKey: ['analytics', 'summary'], queryFn: fetchSummary, refetchInterval: 30000 })
  const { data: funnel } = useQuery({ queryKey: ['analytics', 'funnel'], queryFn: fetchFunnel, refetchInterval: 30000 })
  const { data: podPerf } = useQuery({ queryKey: ['analytics', 'pod-performance'], queryFn: fetchPodPerformance, refetchInterval: 30000 })
  const { data: escalations } = useQuery({ queryKey: ['analytics', 'escalations'], queryFn: fetchEscalations, refetchInterval: 30000 })
  const { data: trend } = useQuery({ queryKey: ['analytics', 'trend'], queryFn: fetchTrend, refetchInterval: 30000 })

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">PM Summary Dashboard</h1>
          <p className="text-sm text-muted-foreground">Request health overview · updates every 30s</p>
        </div>
        <Button variant="outline" size="sm" className="gap-1.5 text-xs h-8">
          📊 Export
        </Button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
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

        <Card>
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

        <Card>
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

        <Card>
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
                <div key={pod} className="border-l-4 border-blue-500 pl-4 py-2">
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
                  <p className="text-sm text-red-700">{escalations.total} requests stuck >{escalations.threshold_days} days</p>
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
