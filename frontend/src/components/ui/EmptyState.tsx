export default function EmptyState({ message = 'No results found' }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-text-muted text-sm font-mono">
      <span className="text-text-muted mr-2">—</span>
      {message}
    </div>
  )
}
