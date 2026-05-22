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
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        PRIORITY_COLORS[priority],
        className
      )}
    >
      {priority}
    </span>
  )
}
