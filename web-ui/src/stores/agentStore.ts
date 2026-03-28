import { create } from 'zustand'
import type { AgentEvent, Agent } from '../types'

interface LogEntry {
  id: number
  event: AgentEvent
  display: { cls: string; source: string; message: string }
}

interface AgentStore {
  agents: Record<string, Agent>
  log: LogEntry[]
  nextId: number
  addEvent: (event: AgentEvent) => void
  clearLog: () => void
}

function formatEvent(event: AgentEvent): { cls: string; source: string; message: string } {
  const source = event.source
  switch (event.type) {
    case 'orchestrator.response':
      return { cls: 'response', source, message: event.data.response || '' }
    case 'orchestrator.plan':
      return { cls: 'delegation', source, message: 'Delegating: ' + (event.data.plan || '') }
    case 'agent.spawned':
      return { cls: 'spawn', source, message: 'Started: ' + (event.data.task || '') }
    case 'agent.step':
      return { cls: 'step', source, message: event.data.action || `step ${event.data.step}: ${(event.data.response || '').slice(0, 100)}` }
    case 'agent.message':
      return { cls: 'delegation', source, message: `-> ${event.data.target}: ${event.data.message || ''}` }
    case 'agent.completed':
      return { cls: 'done', source, message: 'Done: ' + (event.data.answer || '').slice(0, 100) }
    case 'agent.error':
      return { cls: 'error', source, message: 'Error: ' + (event.data.error || '') }
    default:
      return { cls: 'system', source, message: event.data.message || JSON.stringify(event.data).slice(0, 200) }
  }
}

export const useAgentStore = create<AgentStore>((set) => ({
  agents: {},
  log: [],
  nextId: 1,
  addEvent: (event) =>
    set((state) => {
      const agents = { ...state.agents }

      // Update agent status
      if (event.type === 'agent.spawned') {
        agents[event.source] = { name: event.source, status: 'running' }
      } else if (event.type === 'agent.step') {
        if (agents[event.source]) agents[event.source] = { ...agents[event.source], status: 'running' }
      } else if (event.type === 'agent.completed') {
        if (agents[event.source]) agents[event.source] = { ...agents[event.source], status: 'done' }
      } else if (event.type === 'agent.error') {
        if (agents[event.source]) agents[event.source] = { ...agents[event.source], status: 'error' }
      }

      const entry: LogEntry = {
        id: state.nextId,
        event,
        display: formatEvent(event),
      }

      return {
        agents,
        log: [...state.log.slice(-500), entry],
        nextId: state.nextId + 1,
      }
    }),
  clearLog: () => set({ log: [], nextId: 1 }),
}))
