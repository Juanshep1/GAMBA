import { useAgentStore } from '../stores/agentStore'
import type { Agent } from '../types'

const STATUS_COLORS: Record<string, string> = {
  idle: '#71717a',
  running: '#22c55e',
  done: '#06b6d4',
  error: '#ef4444',
}

const STATUS_ICONS: Record<string, string> = {
  idle: '\u25cb',
  running: '\u25cf',
  done: '\u2713',
  error: '\u2717',
}

export function AgentPanel() {
  const agents = useAgentStore((s) => s.agents)
  const entries = Object.values(agents)

  return (
    <div style={{
      width: 200, borderRight: '1px solid #27272a', padding: '16px 12px',
      background: '#0f0f11', flexShrink: 0,
    }}>
      <h3 style={{ color: '#06b6d4', fontSize: '0.85rem', marginBottom: 12, letterSpacing: 1 }}>
        AGENTS
      </h3>
      {entries.length === 0 && (
        <p style={{ color: '#52525b', fontSize: '0.8rem' }}>Waiting for activity...</p>
      )}
      {entries.map((agent) => (
        <AgentCard key={agent.name} agent={agent} />
      ))}
    </div>
  )
}

function AgentCard({ agent }: { agent: Agent }) {
  return (
    <div style={{
      padding: '8px 10px', marginBottom: 6, borderRadius: 6,
      background: '#18181b', border: '1px solid #27272a',
    }}>
      <span style={{ color: STATUS_COLORS[agent.status] || '#71717a', marginRight: 6 }}>
        {STATUS_ICONS[agent.status] || '\u25cb'}
      </span>
      <span style={{ color: '#e4e4e7', fontSize: '0.85rem' }}>{agent.name}</span>
      <span style={{ color: STATUS_COLORS[agent.status], fontSize: '0.7rem', marginLeft: 8 }}>
        {agent.status}
      </span>
    </div>
  )
}
