import { Bug, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { TYPE_COLORS } from '@/lib/constants'
import type { RequestType } from '@/lib/types'

interface TypeBadgeProps {
  type: RequestType
  className?: string
}

export function TypeBadge({ type, className }: TypeBadgeProps) {
  const Icon = type === 'Defect' ? Bug : Sparkles
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs',
        TYPE_COLORS[type],
        className
      )}
    >
      <Icon className="h-3 w-3" />
      {type}
    </span>
  )
}
