import type { JobLog, LogLevel } from '../../types'

const LEVEL_CLS: Record<LogLevel, string> = {
  info:    'border-log-info',
  warning: 'border-log-warning',
  error:   'border-log-error',
  debug:   'border-log-debug',
}

const LEVEL_TEXT_CLS: Record<LogLevel, string> = {
  info:    'text-log-info',
  warning: 'text-log-warning',
  error:   'text-log-error',
  debug:   'text-log-debug',
}

function formatLogTime(iso: string) {
  const d = new Date(iso)
  return d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0')
}

export default function LogTimeline({ logs }: { logs: JobLog[] }) {
  return (
    <div className="bg-bg-base border border-border overflow-y-auto max-h-96">
      {logs.length === 0 ? (
        <p className="text-center text-text-muted text-xs font-mono py-8">No log entries yet</p>
      ) : (
        logs.map((log) => (
          <div
            key={log.id}
            className={`flex gap-3 border-l-2 pl-3 py-2 border-b border-border/30 last:border-b-0 ${LEVEL_CLS[log.level]}`}
          >
            <span className="text-[10px] text-text-muted font-mono whitespace-nowrap shrink-0">
              {formatLogTime(log.created_at)}
            </span>
            <span className={`text-[9px] uppercase w-14 text-right shrink-0 font-mono ${LEVEL_TEXT_CLS[log.level]}`}>
              {log.level}
            </span>
            <span className="text-xs font-mono text-text-primary">{log.message}</span>
          </div>
        ))
      )}
    </div>
  )
}
