import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Copy } from 'lucide-react'
import { getJob, cancelJob } from '../api/jobs'
import { showToast } from '../components/ui/Toast'
import StatusBadge from '../components/ui/StatusBadge'
import PriorityBadge from '../components/ui/PriorityBadge'
import TypeBadge from '../components/ui/TypeBadge'
import JsonViewer from '../components/ui/JsonViewer'
import LogTimeline from '../components/jobs/LogTimeline'

function formatAbs(iso: string) {
  return new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'medium' })
}



function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard', 'info'))
}

export default function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmCancel, setConfirmCancel] = useState(false)

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => getJob(id!),
    refetchInterval: (query) =>
      query.state.data?.status === 'processing' ? 3000 : false,
    enabled: !!id,
  })

  const { mutate: doCancel, isPending: cancelling } = useMutation({
    mutationFn: () => cancelJob(id!),
    onSuccess: () => {
      showToast('Job cancelled', 'warning')
      queryClient.invalidateQueries({ queryKey: ['job', id] })
      setConfirmCancel(false)
    },
    onError: () => {
      showToast('Failed to cancel job', 'error')
      setConfirmCancel(false)
    },
  })

  if (isLoading) {
    return <div className="p-6 text-text-muted text-xs font-mono">loading...</div>
  }

  if (!job) {
    return <div className="p-6 text-status-failed text-xs font-mono">Job not found</div>
  }

  const canCancel = job.status === 'queued' || job.status === 'processing'

  return (
    <div className="p-6">
      <div className="text-xs font-mono text-text-muted mb-5">
        <Link to="/dashboard" className="hover:text-accent transition-colors">Dashboard</Link>
        <span className="mx-2">→</span>
        <span className="text-text-secondary">#{job.id.slice(0, 8)}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <section className="border border-border bg-bg-surface p-4">
            <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-4">Job Info</p>

            <div className="flex items-center gap-3 mb-4">
              <StatusBadge status={job.status} />
              <PriorityBadge priority={job.priority} />
              <TypeBadge type={job.type} />
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex gap-4">
                <span className="text-text-muted w-28">ID</span>
                <div className="flex items-center gap-2">
                  <span className="text-accent break-all">{job.id}</span>
                  <button onClick={() => copyToClipboard(job.id)} className="text-text-muted hover:text-accent">
                    <Copy size={11} />
                  </button>
                </div>
              </div>
              <div className="flex gap-4">
                <span className="text-text-muted w-28">Created</span>
                <span className="text-text-secondary">{formatAbs(job.created_at)}</span>
              </div>
              {job.started_at && (
                <div className="flex gap-4">
                  <span className="text-text-muted w-28">Started</span>
                  <span className="text-text-secondary">{formatAbs(job.started_at)}</span>
                </div>
              )}
              {job.completed_at && (
                <div className="flex gap-4">
                  <span className="text-text-muted w-28">Completed</span>
                  <span className="text-text-secondary">{formatAbs(job.completed_at)}</span>
                </div>
              )}
              <div className="flex gap-4">
                <span className="text-text-muted w-28">Attempts</span>
                <span className="text-text-secondary">{job.attempts} of {job.max_attempts}</span>
              </div>
              {job.next_retry_at && (
                <div className="flex gap-4">
                  <span className="text-text-muted w-28">Next retry</span>
                  <span className="text-status-processing">{formatAbs(job.next_retry_at)}</span>
                </div>
              )}
              {job.idempotency_key && (
                <div className="flex gap-4">
                  <span className="text-text-muted w-28">Idempotency</span>
                  <span className="text-text-secondary break-all">{job.idempotency_key}</span>
                </div>
              )}
            </div>

            {job.error && (
              <div className="mt-4 border-l-2 border-status-failed pl-3 py-1">
                <p className="text-[10px] uppercase tracking-widest text-status-failed font-mono mb-1">Error</p>
                <p className="text-xs font-mono text-text-secondary break-words">{job.error}</p>
              </div>
            )}
          </section>

          {job.result && (
            <section className="border border-border bg-bg-surface p-4">
              <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-3">Result</p>
              <JsonViewer data={job.result} />
            </section>
          )}

          <section className="border border-border bg-bg-surface p-4">
            <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-3">Payload</p>
            <JsonViewer data={job.payload} />
          </section>
        </div>

        <div className="space-y-6">
          <section className="border border-border bg-bg-surface p-4">
            <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-3">
              Logs <span className="text-text-muted">({job.logs.length})</span>
            </p>
            <LogTimeline logs={job.logs} />
          </section>

          {canCancel && (
            <section className="border border-border bg-bg-surface p-4">
              {!confirmCancel ? (
                <button
                  onClick={() => setConfirmCancel(true)}
                  className="w-full border border-status-failed/40 text-status-failed font-mono text-xs py-2 hover:bg-status-failed/10 transition-colors"
                >
                  Cancel Job
                </button>
              ) : (
                <div className="text-xs font-mono">
                  <p className="text-text-secondary mb-3">Confirm cancel?</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => doCancel()}
                      disabled={cancelling}
                      className="flex-1 bg-status-failed/10 border border-status-failed/40 text-status-failed py-1.5 hover:bg-status-failed/20 transition-colors disabled:opacity-50"
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setConfirmCancel(false)}
                      className="flex-1 border border-border text-text-secondary py-1.5 hover:bg-bg-elevated transition-colors"
                    >
                      No
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      </div>

      <div className="mt-6">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-xs font-mono text-text-muted hover:text-accent transition-colors"
        >
          ← Back to Dashboard
        </button>
      </div>
    </div>
  )
}
