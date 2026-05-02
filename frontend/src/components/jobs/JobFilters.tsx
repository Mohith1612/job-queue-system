import type { JobStatus, JobPriority } from '../../types'

interface Filters {
  status: JobStatus | ''
  type: string
  priority: JobPriority | ''
}

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
}

const STATUS_OPTIONS: { value: JobStatus | ''; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'queued', label: 'Queued' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
]

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'email_send', label: 'email_send' },
  { value: 'payment_retry', label: 'payment_retry' },
  { value: 'report_generate', label: 'report_generate' },
]

const PRIORITY_OPTIONS: { value: JobPriority | ''; label: string }[] = [
  { value: '', label: 'All priorities' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const SELECT_CLS =
  'bg-bg-input border border-border text-text-secondary text-xs font-mono px-2 py-1.5 focus:outline-none focus:border-accent'

export default function JobFilters({ filters, onChange }: Props) {
  const hasFilters = filters.status !== '' || filters.type !== '' || filters.priority !== ''

  return (
    <div className="flex items-center gap-3 mb-4 flex-wrap">
      <select
        className={SELECT_CLS}
        value={filters.status}
        onChange={(e) => onChange({ ...filters, status: e.target.value as JobStatus | '' })}
      >
        {STATUS_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      <select
        className={SELECT_CLS}
        value={filters.type}
        onChange={(e) => onChange({ ...filters, type: e.target.value })}
      >
        {TYPE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      <select
        className={SELECT_CLS}
        value={filters.priority}
        onChange={(e) => onChange({ ...filters, priority: e.target.value as JobPriority | '' })}
      >
        {PRIORITY_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {hasFilters && (
        <button
          className="text-[10px] font-mono text-text-muted hover:text-text-secondary border border-border/50 px-2 py-1.5"
          onClick={() => onChange({ status: '', type: '', priority: '' })}
        >
          clear filters
        </button>
      )}
    </div>
  )
}
