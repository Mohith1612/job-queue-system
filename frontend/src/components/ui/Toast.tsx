import { useEffect, useState, useCallback } from 'react'
import { X } from 'lucide-react'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

interface ToastItem {
  id: number
  message: string
  type: ToastType
}

type Listener = (toast: Omit<ToastItem, 'id'>) => void
const listeners: Listener[] = []
let nextId = 0

export function showToast(message: string, type: ToastType = 'info') {
  listeners.forEach((l) => l({ message, type }))
}

const TYPE_STYLES: Record<ToastType, string> = {
  success: 'border-status-completed text-status-completed',
  error:   'border-status-failed    text-status-failed',
  warning: 'border-status-processing text-status-processing',
  info:    'border-accent           text-accent',
}

function Toast({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(item.id), 4000)
    return () => clearTimeout(t)
  }, [item.id, onDismiss])

  return (
    <div
      className={`animate-slide-in flex items-start gap-3 bg-bg-surface border rounded px-4 py-3 shadow-lg max-w-sm ${TYPE_STYLES[item.type]}`}
    >
      <span className="flex-1 text-sm font-mono text-text-primary">{item.message}</span>
      <button onClick={() => onDismiss(item.id)} className="text-text-muted hover:text-text-primary mt-0.5">
        <X size={14} />
      </button>
    </div>
  )
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  useEffect(() => {
    const listener: Listener = (toast) => {
      setToasts((prev) => [...prev, { ...toast, id: nextId++ }])
    }
    listeners.push(listener)
    return () => {
      const idx = listeners.indexOf(listener)
      if (idx !== -1) listeners.splice(idx, 1)
    }
  }, [])

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <Toast key={t.id} item={t} onDismiss={dismiss} />
      ))}
    </div>
  )
}
