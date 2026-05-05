import { useEffect, useState } from 'react'

interface Props {
  seconds: number
  onRefresh: () => void
}

export default function RefreshIndicator({ seconds, onRefresh }: Props) {
  const [remaining, setRemaining] = useState(seconds)

  useEffect(() => {
    setRemaining(seconds)
    const interval = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          onRefresh()
          return seconds
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [seconds, onRefresh])

  const pct = (remaining / seconds) * 100

  return (
    <div className="mb-4">
      <div className="h-0.5 bg-accent/20 w-full overflow-hidden">
        <div
          className="h-full bg-accent transition-[width] duration-1000 ease-linear"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-[10px] font-mono text-text-muted mt-1">
        AUTO-REFRESH IN {remaining}s
      </p>
    </div>
  )
}
