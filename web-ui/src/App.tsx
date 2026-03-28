import { useCallback } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { useAgentStore } from './stores/agentStore'
import { AgentPanel } from './components/AgentPanel'
import { ActivityLog } from './components/ActivityLog'
import { ChatInput } from './components/ChatInput'
import type { AgentEvent } from './types'

export default function App() {
  const addEvent = useAgentStore((s) => s.addEvent)

  const onEvent = useCallback((event: AgentEvent) => {
    addEvent(event)
  }, [addEvent])

  const { connected, send } = useWebSocket(onEvent)

  const handleSend = useCallback((message: string) => {
    // Add user message to log
    addEvent({
      type: 'user.input',
      source: 'you',
      data: { message },
      timestamp: new Date().toISOString(),
    })
    send(message)
  }, [send, addEvent])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid #27272a',
        display: 'flex', alignItems: 'center', gap: 12, background: '#0f0f11',
      }}>
        <h1 style={{ color: '#06b6d4', fontSize: '1.2rem', fontWeight: 'bold' }}>GAMBA</h1>
        <span style={{ color: '#52525b', fontSize: '0.8rem' }}>Multi-Agent Framework</span>
        <div style={{ marginLeft: 'auto' }}>
          <span style={{
            display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
            background: connected ? '#22c55e' : '#ef4444', marginRight: 6,
          }} />
          <span style={{ color: '#71717a', fontSize: '0.75rem' }}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <AgentPanel />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <ActivityLog />
          <ChatInput onSend={handleSend} connected={connected} />
        </div>
      </div>
    </div>
  )
}
