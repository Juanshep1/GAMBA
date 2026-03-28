import { useState, useRef } from 'react'

interface Props {
  onSend: (message: string) => void
  connected: boolean
}

export function ChatInput({ onSend, connected }: Props) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSend = () => {
    const text = value.trim()
    if (!text) return
    onSend(text)
    setValue('')
    inputRef.current?.focus()
  }

  return (
    <div style={{
      display: 'flex', gap: 8, padding: '12px 16px',
      borderTop: '1px solid #27272a', background: '#0f0f11',
    }}>
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
        placeholder={connected ? 'Type a message...' : 'Connecting...'}
        disabled={!connected}
        autoFocus
        style={{
          flex: 1, background: '#18181b', border: '1px solid #27272a',
          borderRadius: 6, color: '#e4e4e7', padding: '10px 14px',
          fontFamily: 'inherit', fontSize: '0.9rem', outline: 'none',
        }}
        onFocus={(e) => (e.target.style.borderColor = '#06b6d4')}
        onBlur={(e) => (e.target.style.borderColor = '#27272a')}
      />
      <button
        onClick={handleSend}
        disabled={!connected}
        style={{
          background: connected ? '#06b6d4' : '#27272a',
          color: '#09090b', border: 'none', borderRadius: 6,
          padding: '10px 20px', fontWeight: 'bold', cursor: connected ? 'pointer' : 'default',
          fontFamily: 'inherit',
        }}
      >
        Send
      </button>
    </div>
  )
}
