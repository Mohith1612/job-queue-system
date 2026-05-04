import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { getMetrics } from '../api/jobs'
import StatCard from '../components/metrics/StatCard'
import QueueDepthBar from '../components/metrics/QueueDepthBar'
import StatusChart from '../components/metrics/StatusChart'
import type { JobStatus } from '../types'

const STATUS_CARDS: { key: JobStatus; label: string; cls: string }[] = [
  { key: 'queued',     label: 'Queued',     cls: 'text-status-queued' },
  { key: 'processing', label: 'Processing', cls: 'text-status-processing' },
  { key: 'completed',  label: 'Completed',  cls: 'text-status-completed' },
  { key: 'failed',     label: 'Failed',     cls: 'text-status-failed' },
  { key: 'cancelled',  label: 'Cancelled',  cls: 'text-status-cancelled' },
]

export default function Metrics() {
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['metrics'],
    queryFn: getMetrics,
    refetchInterval: 10000,
  })

  const queueMax = data
    ? Math.max(data.queue_depths.fifo, data.queue_depths.priority, data.queue_depths.retry, 1)
    : 1

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold tracking-wide uppercase text-text-secondary font-mono">
            System Metrics
          </h1>
          {isFetching && <RefreshCw size={12} className="text-text-muted animate-spin" />}
        </div>
        <button
          onClick={() => refetch()}
          className="border border-border text-text-muted font-mono text-xs px-3 py-1.5 hover:text-text-secondary hover:bg-bg-elevated transition-colors flex items-center gap-2"
        >
          <RefreshCw size={11} />
          Refresh
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-text-muted text-xs font-mono">
          loading...
        </div>
      ) : data ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {STATUS_CARDS.map(({ key, label, cls }) => (
              <StatCard
                key={key}
                label={label}
                value={data.counts_by_status[key] ?? 0}
                valueClass={cls}
              />
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-3 border border-border bg-bg-surface p-4">
              <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-4">
                Status Distribution
              </p>
              <StatusChart counts={data.counts_by_status} />
            </div>

            <div className="lg:col-span-2 border border-border bg-bg-surface p-4">
              <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-4">
                Queue Depths
              </p>
              <QueueDepthBar label="Priority" count={data.queue_depths.priority} max={queueMax} />
              <QueueDepthBar label="FIFO" count={data.queue_depths.fifo} max={queueMax} />
              <QueueDepthBar label="Retry" count={data.queue_depths.retry} max={queueMax} />
            </div>
          </div>

          <div className="border border-border bg-bg-surface p-4 max-w-xs">
            <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-2">
              Avg Processing Time
            </p>
            <p className="text-3xl font-mono text-text-primary">
              {data.avg_processing_time_seconds != null
                ? `${data.avg_processing_time_seconds.toFixed(2)}s`
                : '—'}
            </p>
            <p className="text-text-muted text-xs font-mono mt-1">across all completed jobs</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}
