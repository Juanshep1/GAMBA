import { useEffect, useRef, useState, useCallback } from 'react'
import type { AgentEvent } from '../types'

export function useWebSocket(onEvent: (event: AgentEvent) => void) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      setTimeout(connect, 3000)
    }
    ws.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data))
      } catch {}
    }
  }, [onEvent])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  const send = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'chat', message }))
    }
  }, [])

  return { connected, send }
}
