import client from './client'
import type { Job, JobCreate, JobDetail, JobListParams, JobListResponse, Metrics } from '../types'

export async function createJob(data: JobCreate): Promise<{ job: Job; isReplay: boolean }> {
  const response = await client.post<Job>('/api/v1/jobs', data)
  return {
    job: response.data,
    isReplay: response.headers['x-idempotency-replay'] === 'true',
  }
}

export async function listJobs(params: JobListParams = {}): Promise<JobListResponse> {
  const filtered = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  )
  const response = await client.get<JobListResponse>('/api/v1/jobs', { params: filtered })
  return response.data
}

export async function getJob(id: string): Promise<JobDetail> {
  const response = await client.get<JobDetail>(`/api/v1/jobs/${id}`)
  return response.data
}

export async function cancelJob(id: string): Promise<Job> {
  const response = await client.post<Job>(`/api/v1/jobs/${id}/cancel`)
  return response.data
}

export async function getMetrics(): Promise<Metrics> {
  const response = await client.get<Metrics>('/api/v1/metrics')
  return response.data
}
