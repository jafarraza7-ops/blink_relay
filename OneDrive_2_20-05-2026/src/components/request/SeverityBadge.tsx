import { cn } from '@/lib/utils'
import { SEVERITY_COLORS } from '@/lib/constants'
import type { Severity } from '@/lib/types'

interface SeverityBadgeProps {
  severity: Severity
  className?: string
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        SEVERITY_COLORS[severity],
        className
      )}
    >
      {severity}
    </span>
  )
}
