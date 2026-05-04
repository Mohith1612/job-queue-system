interface Props {
  label: string
  count: number
  max: number
}

export default function QueueDepthBar({ label, count, max }: Props) {
  const pct = max > 0 ? Math.min((count / max) * 100, 100) : 0

  return (
    <div className="mb-4">
      <div className="flex justify-between text-[10px] font-mono mb-1.5">
        <span className="text-text-muted uppercase tracking-wider">{label}</span>
        <span className="text-text-secondary">{count}</span>
      </div>
      <div className="h-1.5 bg-bg-base border border-border">
        <div
          className="h-full bg-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
