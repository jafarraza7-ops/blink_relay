import { formatDateTime } from '@/lib/utils'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2, Clock, AlertCircle, FileCheck, Info } from 'lucide-react'

export interface TimelineEvent {
  timestamp: string
  action: string
  actor_name: string
  actor_email?: string
  details: string
  status?: string
}

/**
 * RequestTimeline — Visual timeline of request lifecycle events.
 *
 * Renders a vertical timeline showing all status changes, approvals,
 * rejections, and clarifications with icons, actor info, and timestamps.
 * Maps action types to appropriate icons and colors for quick visual scanning.
 */
export function RequestTimeline({ events }: { events: TimelineEvent[] }) {
  // Map action types to icons and colors
  const getActionIcon = (action: string) => {
    switch (action) {
      case 'submitted':
        return <Clock className="h-5 w-5 text-blue-500" />
      case 'approved':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />
      case 'rejected':
        return <AlertCircle className="h-5 w-5 text-red-500" />
      case 'info_provided':
        return <Info className="h-5 w-5 text-purple-500" />
      case 'request_cancelled':
        return <AlertCircle className="h-5 w-5 text-gray-500" />
      case 'status_change':
        return <FileCheck className="h-5 w-5 text-purple-500" />
      default:
        return <Clock className="h-5 w-5 text-gray-500" />
    }
  }

  const getActionLabel = (action: string) => {
    switch (action) {
      case 'submitted':
        return 'Request Submitted'
      case 'approved':
        return 'Request Approved'
      case 'rejected':
        return 'Request Rejected'
      case 'info_provided':
        return 'Information Provided'
      case 'request_cancelled':
        return 'Request Cancelled'
      case 'status_change':
        return 'Status Changed'
      default:
        return action.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
    }
  }

  if (events.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-muted-foreground">
        No timeline events available
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {events.map((event, index) => (
        <div key={index} className="flex gap-4">
          {/* Timeline marker and connector */}
          <div className="flex flex-col items-center">
            <div className="p-2 rounded-full bg-gray-100">
              {getActionIcon(event.action)}
            </div>
            {index < events.length - 1 && (
              <div className="w-0.5 h-12 bg-gray-200 my-2" />
            )}
          </div>

          {/* Event details */}
          <Card className="flex-1 p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h4 className="font-semibold text-sm">{getActionLabel(event.action)}</h4>
                <p className="text-sm text-gray-600 mt-1">{event.details}</p>
                <p className="text-xs text-gray-500 mt-2">
                  By {event.actor_name} {event.actor_email && `(${event.actor_email})`}
                </p>
              </div>
              <div className="text-right ml-4">
                <p className="text-xs text-gray-500 whitespace-nowrap">{formatDateTime(event.timestamp)}</p>
                {event.status && (
                  <Badge className="mt-2">{event.status}</Badge>
                )}
              </div>
            </div>
          </Card>
        </div>
      ))}
    </div>
  )
}
