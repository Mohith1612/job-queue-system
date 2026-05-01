import type { JobStatus } from '../../types'

const CONFIG: Record<JobStatus, { dot: string; text: string; bg: string }> = {
  queued:     { dot: 'bg-status-queued',     text: 'text-status-queued',     bg: 'bg-status-queued/10' },
  processing: { dot: 'bg-status-processing', text: 'text-status-processing', bg: 'bg-status-processing/10' },
  completed:  { dot: 'bg-status-completed',  text: 'text-status-completed',  bg: 'bg-status-completed/10' },
  failed:     { dot: 'bg-status-failed',     text: 'text-status-failed',     bg: 'bg-status-failed/10' },
  cancelled:  { dot: 'bg-status-cancelled',  text: 'text-status-cancelled',  bg: 'bg-status-cancelled/10' },
}

export default function StatusBadge({ status }: { status: JobStatus }) {
  const c = CONFIG[status]
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono ${c.bg}`}>
      <span
        className={`w-1.5 h-1.5 rounded-full ${c.dot} ${status === 'processing' ? 'animate-pulse-dot' : ''}`}
      />
      <span className={c.text}>{status}</span>
    </span>
  )
}
