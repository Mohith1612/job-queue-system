import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import type { JobPriority } from '../types'
import { createJob } from '../api/jobs'
import { showToast } from '../components/ui/Toast'
import { RateLimitError } from '../api/client'
import JsonViewer from '../components/ui/JsonViewer'
import PriorityBadge from '../components/ui/PriorityBadge'
import TypeBadge from '../components/ui/TypeBadge'

const PRESETS = {
  failing: {
    type: 'payment_retry',
    priority: 'medium' as JobPriority,
    max_attempts: 3,
    payload: { amount: 99.99, currency: 'USD', customer_id: 'cust_demo' },
  },
  high_priority: {
    type: 'email_send',
    priority: 'high' as JobPriority,
    max_attempts: 5,
    payload: { to: 'demo@example.com', subject: 'Urgent notification', body: 'Test' },
  },
  retry_heavy: {
    type: 'payment_retry',
    priority: 'low' as JobPriority,
    max_attempts: 10,
    payload: { amount: 250.0, currency: 'USD', customer_id: 'cust_retry' },
  },
} as const

const JOB_TYPES = ['email_send', 'payment_retry', 'report_generate']
const PRIORITIES: JobPriority[] = ['high', 'medium', 'low']

const PRIORITY_CLS: Record<JobPriority, string> = {
  high: 'border-priority-high text-priority-high',
  medium: 'border-priority-medium text-priority-medium',
  low: 'border-priority-low text-priority-low',
}

export default function CreateJob() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [jobType, setJobType] = useState('email_send')
  const [priority, setPriority] = useState<JobPriority>('medium')
  const [payloadStr, setPayloadStr] = useState('{\n  \n}')
  const [idempotencyKey, setIdempotencyKey] = useState('')
  const [maxAttempts, setMaxAttempts] = useState(5)
  const [submitting, setSubmitting] = useState(false)
  const [rateLimited, setRateLimited] = useState(false)

  const applyPreset = useCallback((key: keyof typeof PRESETS) => {
    const p = PRESETS[key]
    setJobType(p.type)
    setPriority(p.priority)
    setMaxAttempts(p.max_attempts)
    setPayloadStr(JSON.stringify(p.payload, null, 2))
  }, [])

  useEffect(() => {
    const preset = searchParams.get('preset')
    if (preset && preset in PRESETS) {
      applyPreset(preset as keyof typeof PRESETS)
    }
  }, [searchParams, applyPreset])

  const payloadValid = (() => {
    try { JSON.parse(payloadStr); return true } catch { return false }
  })()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!payloadValid || submitting || rateLimited) return

    setSubmitting(true)
    try {
      const { job, isReplay } = await createJob({
        type: jobType,
        payload: JSON.parse(payloadStr),
        priority,
        ...(idempotencyKey ? { idempotency_key: idempotencyKey } : {}),
        max_attempts: maxAttempts,
      })
      const short = job.id.slice(0, 8)
      showToast(
        isReplay
          ? `Idempotency hit — returning existing job #${short}`
          : `Job created — #${short}`,
        isReplay ? 'warning' : 'success'
      )
      navigate(`/jobs/${job.id}`)
    } catch (err) {
      if (err instanceof RateLimitError) {
        showToast('Rate limit exceeded — please wait before submitting more jobs', 'error')
        setRateLimited(true)
        setTimeout(() => setRateLimited(false), 3000)
      } else {
        showToast('Failed to create job', 'error')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const inputCls = 'w-full bg-bg-input border border-border text-text-primary text-sm font-mono px-3 py-2 focus:outline-none focus:border-accent'

  const parsedPayload = (() => {
    try { return JSON.parse(payloadStr) } catch { return null }
  })()

  return (
    <div className="p-6">
      <h1 className="text-base font-semibold tracking-wide uppercase text-text-secondary font-mono mb-5">
        Create Job
      </h1>

      <div className="mb-6">
        <p className="text-[10px] tracking-widest text-text-muted font-mono mb-3">QUICK PRESETS</p>
        <div className="flex gap-3 flex-wrap">
          {(Object.keys(PRESETS) as (keyof typeof PRESETS)[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => applyPreset(key)}
              className="border border-border text-text-secondary hover:bg-bg-elevated font-mono text-xs px-3 py-1.5 transition-colors"
            >
              {key === 'failing' ? 'Failing Job' : key === 'high_priority' ? 'High Priority' : 'Retry Heavy'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-6 items-start">
        {/* Form — 60% */}
        <form onSubmit={handleSubmit} className="flex-[3] min-w-0 space-y-5">
          <div>
            <label className="block text-[10px] tracking-widest text-text-muted font-mono mb-1.5">JOB TYPE</label>
            <select
              className={inputCls}
              value={jobType}
              onChange={(e) => setJobType(e.target.value)}
            >
              {JOB_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-[10px] tracking-widest text-text-muted font-mono mb-1.5">PRIORITY</label>
            <div className="flex gap-2">
              {PRIORITIES.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPriority(p)}
                  className={`flex-1 py-1.5 text-xs font-mono uppercase tracking-wider border transition-colors ${
                    priority === p
                      ? PRIORITY_CLS[p]
                      : 'border-border text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[10px] tracking-widest text-text-muted font-mono mb-1.5">
              PAYLOAD <span className={`ml-2 ${payloadValid ? 'text-status-completed' : 'text-status-failed'}`}>
                {payloadValid ? '✓ valid json' : '✗ invalid json'}
              </span>
            </label>
            <textarea
              rows={8}
              className={`${inputCls} resize-y ${!payloadValid ? 'border-status-failed' : ''}`}
              value={payloadStr}
              onChange={(e) => setPayloadStr(e.target.value)}
              spellCheck={false}
            />
          </div>

          <div>
            <label className="block text-[10px] tracking-widest text-text-muted font-mono mb-1.5">
              IDEMPOTENCY KEY <span className="text-text-muted">(optional)</span>
            </label>
            <input
              type="text"
              className={inputCls}
              value={idempotencyKey}
              onChange={(e) => setIdempotencyKey(e.target.value)}
              placeholder="leave empty for auto-generated"
            />
          </div>

          <div>
            <label className="block text-[10px] tracking-widest text-text-muted font-mono mb-1.5">MAX ATTEMPTS</label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="border border-border text-text-secondary w-8 h-8 font-mono hover:bg-bg-elevated disabled:opacity-30"
                disabled={maxAttempts <= 1}
                onClick={() => setMaxAttempts((n) => Math.max(1, n - 1))}
              >
                −
              </button>
              <span className="text-text-primary font-mono text-sm w-4 text-center">{maxAttempts}</span>
              <button
                type="button"
                className="border border-border text-text-secondary w-8 h-8 font-mono hover:bg-bg-elevated disabled:opacity-30"
                disabled={maxAttempts >= 10}
                onClick={() => setMaxAttempts((n) => Math.min(10, n + 1))}
              >
                +
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={!payloadValid || submitting || rateLimited}
            className="w-full bg-accent text-bg-base font-mono text-sm py-2.5 hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {rateLimited ? 'Rate limited — wait...' : submitting ? 'Submitting...' : 'Submit Job'}
          </button>
        </form>

        {/* Preview — 40% */}
        <div className="flex-[2] min-w-0 border border-border bg-bg-surface p-4 space-y-4 sticky top-6">
          <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono">Live Preview</p>

          <div className="flex items-center gap-2 flex-wrap">
            <TypeBadge type={jobType} />
            <PriorityBadge priority={priority} />
            <span className="text-[10px] font-mono text-text-muted">×{maxAttempts}</span>
          </div>

          <div>
            <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-2">Payload</p>
            {payloadValid ? (
              <JsonViewer data={parsedPayload} />
            ) : (
              <p className="text-[10px] font-mono text-status-failed">invalid json</p>
            )}
          </div>

          {idempotencyKey && (
            <div>
              <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-1">Idempotency Key</p>
              <p className="text-xs font-mono text-text-secondary break-all">{idempotencyKey}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
