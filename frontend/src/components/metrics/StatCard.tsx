interface Props {
  label: string
  value: number
  valueClass?: string
  sublabel?: string
}

export default function StatCard({ label, value, valueClass = 'text-text-primary', sublabel }: Props) {
  return (
    <div className="bg-bg-surface border border-border p-4">
      <p className="text-[10px] uppercase tracking-widest text-text-muted font-mono mb-2">{label}</p>
      <p className={`text-3xl font-mono ${valueClass}`}>{value.toLocaleString()}</p>
      {sublabel && <p className="text-text-muted text-xs font-mono mt-1">{sublabel}</p>}
    </div>
  )
}
