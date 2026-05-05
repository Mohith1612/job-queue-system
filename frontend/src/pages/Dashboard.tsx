import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listJobs } from '../api/jobs'
import type { JobStatus, JobPriority } from '../types'
import JobFilters from '../components/jobs/JobFilters'
import JobTable from '../components/jobs/JobTable'
import RefreshIndicator from '../components/ui/RefreshIndicator'

interface Filters {
  status: JobStatus | ''
  type: string
  priority: JobPriority | ''
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<Filters>({ status: '', type: '', priority: '' })

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['jobs', page, filters],
    queryFn: () =>
      listJobs({
        page,
        page_size: 20,
        ...(filters.status ? { status: filters.status } : {}),
        ...(filters.type ? { type: filters.type } : {}),
        ...(filters.priority ? { priority: filters.priority } : {}),
      }),
  })

  const doRefresh = useCallback(() => { refetch() }, [refetch])

  function handleFiltersChange(f: Filters) {
    setFilters(f)
    setPage(1)
  }

  return (
    <div className="p-6">
      <RefreshIndicator seconds={5} onRefresh={doRefresh} />
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-base font-semibold tracking-wide uppercase text-text-secondary font-mono">
          Jobs
        </h1>
        <button
          onClick={() => navigate('/create')}
          className="bg-accent text-bg-base font-mono text-xs px-4 py-2 hover:bg-accent/90 transition-colors"
        >
          Create Job →
        </button>
      </div>

      <JobFilters filters={filters} onChange={handleFiltersChange} />

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-text-muted text-xs font-mono">
          loading...
        </div>
      ) : (
        <JobTable
          jobs={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={20}
          onPageChange={setPage}
        />
      )}
    </div>
  )
}
