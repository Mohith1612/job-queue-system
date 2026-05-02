import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { Job } from '../../types'
import StatusBadge from '../ui/StatusBadge'
import PriorityBadge from '../ui/PriorityBadge'
import TypeBadge from '../ui/TypeBadge'
import EmptyState from '../ui/EmptyState'

interface Props {
  jobs: Job[]
  total: number
  page: number
  pageSize: number
  onPageChange: (p: number) => void
}

function formatDuration(job: Job): { text: string; cls: string } {
  if (job.status === 'processing') return { text: 'running...', cls: 'text-status-processing' }
  if (!job.started_at || !job.completed_at) return { text: '—', cls: 'text-text-muted' }
  const ms = new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()
  return { text: `${(ms / 1000).toFixed(1)}s`, cls: 'text-text-secondary' }
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })
}

export default function JobTable({ jobs, total, page, pageSize, onPageChange }: Props) {
  const navigate = useNavigate()
  const totalPages = Math.ceil(total / pageSize)
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div>
      <div className="border border-border overflow-x-auto">
        <table className="w-full text-sm font-mono">
          <thead>
            <tr className="border-b border-border">
              {['ID', 'TYPE', 'PRIORITY', 'STATUS', 'ATTEMPTS', 'CREATED', 'DURATION'].map((h) => (
                <th
                  key={h}
                  className="text-[10px] uppercase tracking-widest text-text-muted px-3 py-2 text-left font-normal"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <EmptyState message="No jobs found" />
                </td>
              </tr>
            ) : (
              jobs.map((job) => {
                const dur = formatDuration(job)
                return (
                  <tr
                    key={job.id}
                    className="border-b border-border/50 hover:bg-bg-elevated cursor-pointer transition-colors duration-100"
                    onClick={() => navigate(`/jobs/${job.id}`)}
                  >
                    <td className="px-3 py-2.5 text-accent text-xs">
                      {job.id.slice(0, 8)}…
                    </td>
                    <td className="px-3 py-2.5">
                      <TypeBadge type={job.type} />
                    </td>
                    <td className="px-3 py-2.5">
                      <PriorityBadge priority={job.priority} />
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-3 py-2.5 text-text-secondary text-xs">
                      {job.attempts} / {job.max_attempts}
                    </td>
                    <td className="px-3 py-2.5 text-text-muted text-xs">
                      {formatDate(job.created_at)}
                    </td>
                    <td className={`px-3 py-2.5 text-xs ${dur.cls}`}>
                      {dur.text}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {total > 0 && (
        <div className="flex items-center justify-between mt-3 text-xs font-mono text-text-muted">
          <span>Showing {start}–{end} of {total} jobs</span>
          <div className="flex items-center gap-2">
            <button
              className="p-1 hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft size={14} />
            </button>
            <span>Page {page} of {totalPages}</span>
            <button
              className="p-1 hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
