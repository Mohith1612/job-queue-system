import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import type { JobStatus } from '../../types'

const STATUS_COLORS: Record<JobStatus, string> = {
  queued:     '#388bfd',
  processing: '#d29922',
  completed:  '#3fb950',
  failed:     '#f85149',
  cancelled:  '#484f58',
}

interface Props {
  counts: Record<JobStatus, number>
}

export default function StatusChart({ counts }: Props) {
  const data = (Object.entries(counts) as [JobStatus, number][]).map(([status, count]) => ({
    status,
    count,
    fill: STATUS_COLORS[status],
  }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
        <CartesianGrid stroke="#21262d" vertical={false} />
        <XAxis
          dataKey="status"
          tick={{ fill: '#8b949e', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: '#8b949e', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip
          cursor={{ fill: '#161b22' }}
          contentStyle={{
            backgroundColor: '#0d1117',
            border: '1px solid #21262d',
            borderRadius: 0,
            fontFamily: 'IBM Plex Mono',
            fontSize: 12,
            color: '#e6edf3',
          }}
          labelStyle={{ color: '#8b949e' }}
        />
        <Bar dataKey="count" radius={0}>
          {data.map((entry) => (
            <Cell key={entry.status} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
