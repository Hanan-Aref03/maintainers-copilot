import { useState } from 'react'

const DEFAULT_API_URL = 'http://localhost:8010'
const DEFAULT_WIDGET_ID = 'widget123'

function readWidgetConfig() {
  if (typeof document === 'undefined') {
    return {
      apiUrl: DEFAULT_API_URL,
      widgetId: DEFAULT_WIDGET_ID,
    }
  }

  const scriptTag = document.querySelector('script[data-widget-id]')
  const widgetId = scriptTag?.dataset?.widgetId ?? DEFAULT_WIDGET_ID

  let apiUrl = DEFAULT_API_URL
  if (scriptTag?.src) {
    try {
      apiUrl = new URL(scriptTag.src).origin
    } catch {
      apiUrl = DEFAULT_API_URL
    }
  }

  return {
    apiUrl,
    widgetId,
  }
}

const widgetConfig = readWidgetConfig()

export default function App() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)

  const sendMessage = async () => {
    const prompt = input.trim()
    if (!prompt || isSending) return

    setIsSending(true)
    setMessages(prev => [...prev, { role: 'user', content: prompt }])
    setInput('')

    try {
      const url = new URL('/chat/', widgetConfig.apiUrl)
      url.searchParams.set('message', prompt)
      url.searchParams.set('thread_id', widgetConfig.widgetId)

      const response = await fetch(url.toString(), {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      const data = await response.json()
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.response ?? 'No response received.',
        },
      ])
    } catch {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I could not reach the assistant right now.',
        },
      ])
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 9999 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: '#3b82f6',
          color: 'white',
          border: 'none',
          borderRadius: 999,
          padding: '12px 20px',
          cursor: 'pointer',
          boxShadow: '0 10px 24px rgba(59, 130, 246, 0.28)',
        }}
      >
        {open ? 'Close' : 'Chat'}
      </button>
      {open && (
        <div
          style={{
            width: 350,
            height: 500,
            background: 'white',
            border: '1px solid #ccc',
            borderRadius: 12,
            marginTop: 10,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            boxShadow: '0 24px 48px rgba(15, 23, 42, 0.18)',
          }}
        >
          <div
            style={{
              padding: 12,
              background: '#3b82f6',
              color: 'white',
              borderTopLeftRadius: 12,
              borderTopRightRadius: 12,
              fontWeight: 600,
            }}
          >
            Maintainer's Copilot
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {messages.map((message, index) => (
              <div
                key={index}
                style={{
                  marginBottom: 8,
                  textAlign: message.role === 'user' ? 'right' : 'left',
                }}
              >
                <strong>{message.role === 'user' ? 'You' : 'Bot'}:</strong>{' '}
                {message.content}
              </div>
            ))}
          </div>
          <div
            style={{
              padding: 12,
              borderTop: '1px solid #eee',
              display: 'flex',
              gap: 8,
            }}
          >
            <input
              value={input}
              onChange={event => setInput(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  void sendMessage()
                }
              }}
              placeholder="Ask about this repository..."
              style={{
                flex: 1,
                padding: 8,
                borderRadius: 20,
                border: '1px solid #ccc',
              }}
            />
            <button
              onClick={() => void sendMessage()}
              disabled={isSending || !input.trim()}
              style={{
                background: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: 20,
                padding: '8px 16px',
                opacity: isSending || !input.trim() ? 0.7 : 1,
                cursor: isSending || !input.trim() ? 'not-allowed' : 'pointer',
              }}
            >
              {isSending ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
