interface Props {
  data: Record<string, unknown> | null | undefined
}

function colorize(json: string): string {
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      let cls = 'color:#3fb950'
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = 'color:#58a6ff'
        }
      } else if (/true|false|null/.test(match)) {
        cls = 'color:#f85149'
      } else {
        cls = 'color:#d29922'
      }
      return `<span style="${cls}">${match}</span>`
    }
  )
}

export default function JsonViewer({ data }: Props) {
  if (!data) return null
  const formatted = JSON.stringify(data, null, 2)

  return (
    <pre
      className="bg-bg-base border border-border rounded p-3 text-xs font-code text-text-secondary overflow-x-auto whitespace-pre-wrap"
      dangerouslySetInnerHTML={{ __html: colorize(formatted) }}
    />
  )
}
