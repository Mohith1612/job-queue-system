export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
export type JobPriority = 'high' | 'medium' | 'low'
export type JobType = 'email_send' | 'payment_retry' | 'report_generate'
export type LogLevel = 'info' | 'warning' | 'error' | 'debug'

export interface JobLog {
  id: string
  job_id: string
  level: LogLevel
  message: string
  created_at: string
}

export interface Job {
  id: string
  type: string
  payload: Record<string, unknown>
  priority: JobPriority
  status: JobStatus
  idempotency_key: string | null
  attempts: number
  max_attempts: number
  next_retry_at: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: string | null
  result: Record<string, unknown> | null
}

export interface JobDetail extends Job {
  logs: JobLog[]
}

export interface JobListResponse {
  items: Job[]
  total: number
  page: number
  page_size: number
}

export interface QueueDepths {
  fifo: number
  priority: number
  retry: number
}

export interface Metrics {
  counts_by_status: Record<JobStatus, number>
  avg_processing_time_seconds: number | null
  queue_depths: QueueDepths
}

export interface JobCreate {
  type: string
  payload: Record<string, unknown>
  priority: JobPriority
  idempotency_key?: string
  max_attempts?: number
}

export interface JobListParams {
  status?: JobStatus
  type?: string
  priority?: JobPriority
  page?: number
  page_size?: number
}
