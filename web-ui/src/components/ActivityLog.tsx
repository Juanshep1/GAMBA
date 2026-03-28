import { useEffect, useRef } from 'react'
import { useAgentStore } from '../stores/agentStore'

const CLS_COLORS: Record<string, string> = {
  response: '#e4e4e7',
  delegation: '#eab308',
  spawn: '#22c55e',
  step: '#71717a',
  done: '#06b6d4',
  error: '#ef4444',
  system: '#52525b',
}

export function ActivityLog() {
  const log = useAgentStore((s) => s.log)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [log.length])

  return (
    <div style={{
      flex: 1, overflowY: 'auto', padding: '12px 16px',
      background: '#09090b', fontSize: '0.85rem', lineHeight: 1.7,
    }}>
      {log.map((entry) => {
        const ts = new Date(entry.event.timestamp).toLocaleTimeString()
        const color = CLS_COLORS[entry.display.cls] || '#a1a1aa'
        const srcColor = entry.display.cls === 'response' ? '#22c55e' : '#06b6d4'
        return (
          <div key={entry.id} style={{ marginBottom: 2 }}>
            <span style={{ color: '#52525b' }}>{ts} </span>
            <span style={{ color: srcColor, fontWeight: 'bold' }}>[{entry.display.source}] </span>
            <span style={{ color }}>{entry.display.message}</span>
          </div>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}
