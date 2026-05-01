const LABELS: Record<string, string> = {
  email_send:      'email_send',
  payment_retry:   'payment_retry',
  report_generate: 'report_generate',
}

export default function TypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-block px-1.5 py-0.5 text-[10px] font-mono text-text-secondary border border-border rounded-sm">
      {LABELS[type] ?? type}
    </span>
  )
}
