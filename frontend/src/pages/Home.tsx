import { useNavigate } from 'react-router-dom'

const FEATURES = [
  'Background job execution with async workers',
  'Retry with exponential backoff and jitter',
  'Idempotent APIs — duplicate safe via unique keys',
  'Priority-based scheduling (high / medium / low)',
  'Observability — metrics + per-job execution logs',
]

export default function Home() {
  const navigate = useNavigate()

  return (
    <div
      className="min-h-screen bg-bg-base flex items-center justify-center"
      style={{
        backgroundImage:
          'repeating-linear-gradient(0deg, transparent, transparent 39px, #161b22 39px, #161b22 40px), repeating-linear-gradient(90deg, transparent, transparent 39px, #161b22 39px, #161b22 40px)',
      }}
    >
      <div className="max-w-2xl w-full px-8 py-16">
        <p className="text-text-muted text-[10px] tracking-[0.4em] font-mono mb-6">
          DISTRIBUTED SYSTEMS · DEMO PROJECT
        </p>

        <h1 className="text-3xl font-mono text-text-primary mb-3">
          Distributed Job Queue System
        </h1>
        <p className="text-text-secondary text-sm font-mono max-w-lg mb-8">
          Async processing, retries, idempotency, and priority scheduling — built with FastAPI, PostgreSQL, and Redis.
        </p>

        <ul className="space-y-2 mb-10">
          {FEATURES.map((f) => (
            <li key={f} className="flex items-start gap-3 text-sm font-mono text-text-secondary">
              <span className="text-accent mt-0.5 select-none">▸</span>
              {f}
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-4 mb-12">
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-accent text-bg-base font-mono text-sm px-6 py-2.5 hover:bg-accent/90 transition-colors"
          >
            → Open Dashboard
          </button>
          <button
            onClick={() => navigate('/metrics')}
            className="border border-border text-text-secondary font-mono text-sm px-6 py-2.5 hover:text-text-primary hover:border-border transition-colors"
          >
            View Metrics →
          </button>
        </div>

        <div className="border-t border-border pt-8">
          <p className="text-[10px] tracking-widest text-text-muted font-mono mb-4">QUICK DEMO</p>
          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={() => navigate('/create?preset=failing')}
              className="border border-border text-text-secondary hover:bg-bg-elevated font-mono text-xs px-3 py-1.5 transition-colors"
            >
              Simulate Failure Job
            </button>
            <button
              onClick={() => navigate('/create?preset=high_priority')}
              className="border border-border text-text-secondary hover:bg-bg-elevated font-mono text-xs px-3 py-1.5 transition-colors"
            >
              High Priority Job
            </button>
            <button
              onClick={() => navigate('/create?preset=retry_heavy')}
              className="border border-border text-text-secondary hover:bg-bg-elevated font-mono text-xs px-3 py-1.5 transition-colors"
            >
              Retry-Heavy Job
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
