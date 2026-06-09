import { cn } from '@/lib/utils'
import { POD_COLORS, POD_LABELS } from '@/lib/constants'
import type { Pod } from '@/lib/types'

interface PodBadgeProps {
  pod: Pod
  className?: string
}

export function PodBadge({ pod, className }: PodBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        POD_COLORS[pod],
        className
      )}
    >
      {POD_LABELS[pod]}
    </span>
  )
}
