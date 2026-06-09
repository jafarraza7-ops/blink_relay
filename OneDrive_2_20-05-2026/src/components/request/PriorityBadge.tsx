import { cn } from '@/lib/utils'
import { PRIORITY_COLORS } from '@/lib/constants'
import type { Priority } from '@/lib/types'

interface PriorityBadgeProps {
  priority: Priority
  className?: string
}

export function PriorityBadge({ priority, className }: PriorityBadgeProps) {
  return (
    <span
      className={cn(
        'text-xs',
        PRIORITY_COLORS[priority],
        className
      )}
    >
      {priority}
    </span>
  )
}
