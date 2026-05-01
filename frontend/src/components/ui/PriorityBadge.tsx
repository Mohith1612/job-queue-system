import type { JobPriority } from '../../types'

const CONFIG: Record<JobPriority, string> = {
  high:   'border-priority-high/40   text-priority-high',
  medium: 'border-priority-medium/40 text-priority-medium',
  low:    'border-priority-low/40    text-priority-low',
}

export default function PriorityBadge({ priority }: { priority: JobPriority }) {
  return (
    <span
      className={`inline-block px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded-sm ${CONFIG[priority]}`}
    >
      {priority}
    </span>
  )
}
