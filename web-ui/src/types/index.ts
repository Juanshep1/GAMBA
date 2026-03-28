export interface AgentEvent {
  type: string
  source: string
  data: Record<string, string>
  timestamp: string
}

export interface Agent {
  name: string
  status: 'idle' | 'running' | 'done' | 'error'
}
