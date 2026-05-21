import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

const DEFAULT_API_URL = 'http://localhost:8010'
const DEFAULT_WIDGET_ID = 'widget123'
const DEFAULT_THEME = {
  primary_color: '#0f766e',
  position: 'bottom-right',
}

function readWidgetConfig() {
  const runtimeConfig = typeof window !== 'undefined' ? window.__COPILOT_WIDGET_CONFIG__ ?? {} : {}
  const scriptTag = typeof document !== 'undefined' ? document.querySelector('script[data-widget-id]') : null

  const scriptOrigin = (() => {
    if (!scriptTag?.src) {
      return DEFAULT_API_URL
    }
    try {
      return new URL(scriptTag.src).origin
    } catch {
      return DEFAULT_API_URL
    }
  })()

  return {
    apiUrl: runtimeConfig.apiUrl ?? scriptOrigin ?? DEFAULT_API_URL,
    widgetId: runtimeConfig.widgetId ?? scriptTag?.dataset?.widgetId ?? DEFAULT_WIDGET_ID,
    theme: {
      ...DEFAULT_THEME,
      ...(runtimeConfig.theme ?? {}),
      primary_color: runtimeConfig.theme?.primary_color ?? runtimeConfig.theme?.primaryColor ?? DEFAULT_THEME.primary_color,
      position: runtimeConfig.theme?.position ?? DEFAULT_THEME.position,
    },
    greeting: runtimeConfig.greeting ?? 'Hi! How can I help with issue triage?',
    enabledTools: Array.isArray(runtimeConfig.enabledTools) ? runtimeConfig.enabledTools : ['classify', 'rag', 'memory'],
  }
}

const widgetConfig = readWidgetConfig()

function sanitizeMessage(text) {
  return String(text ?? '').replace(/\s+/g, ' ').trim()
}

export default function App() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState(() =>
    widgetConfig.greeting
      ? [{ role: 'assistant', content: widgetConfig.greeting }]
      : [],
  )
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const messageListRef = useRef(null)
  const primaryColor = widgetConfig.theme.primary_color

  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight
    }
  }, [messages, open])

  useEffect(() => {
    const height = open ? 620 : 84
    window.parent?.postMessage(
      {
        type: 'copilot-widget:resize',
        widgetId: widgetConfig.widgetId,
        height,
      },
      '*',
    )
  }, [open, messages.length])

  const positionStyle = useMemo(
    () =>
      widgetConfig.theme.position === 'bottom-left'
        ? { left: '20px', right: 'auto' }
        : { right: '20px', left: 'auto' },
    [],
  )
  const alignItems = widgetConfig.theme.position === 'bottom-left' ? 'flex-start' : 'flex-end'

  const sendMessage = async () => {
    const prompt = sanitizeMessage(input)
    if (!prompt || isSending) return

    setIsSending(true)
    setMessages(prev => [...prev, { role: 'user', content: prompt }])
    setInput('')

    try {
      const url = new URL(`/widgets/${widgetConfig.widgetId}/chat`, widgetConfig.apiUrl)
      url.searchParams.set('message', prompt)

      const response = await fetch(url.toString(), {
        method: 'POST',
        headers: {
          'Content-Type': 'text/plain',
        },
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
    <div className="copilot-widget" style={{ ...positionStyle, alignItems }}>
      <button
        className="copilot-launcher"
        onClick={() => setOpen(!open)}
        style={{
          background: `linear-gradient(135deg, ${primaryColor}, #111827)`,
          boxShadow: '0 18px 36px rgba(15, 118, 110, 0.38)',
        }}
      >
        <span className="copilot-launcher-dot" />
        {open ? 'Close' : 'Ask Copilot'}
      </button>

      {open ? (
        <div className="copilot-panel">
          <div className="copilot-header" style={{ background: `linear-gradient(135deg, ${primaryColor}, #111827)` }}>
            <div>
              <div className="copilot-eyebrow">Maintainer’s Copilot</div>
              <div className="copilot-title">Issue triage, memory, and docs search</div>
            </div>
            <button className="copilot-close" onClick={() => setOpen(false)} aria-label="Close widget">
              ×
            </button>
          </div>

          <div className="copilot-toolbar">
            {widgetConfig.enabledTools.slice(0, 3).map(tool => (
              <span key={tool} className="copilot-chip">
                {tool}
              </span>
            ))}
          </div>

          <div className="copilot-messages" ref={messageListRef}>
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`copilot-message copilot-message--${message.role}`}
              >
                <div className="copilot-message-role">
                  {message.role === 'user' ? 'You' : 'Copilot'}
                </div>
                <div className="copilot-message-bubble">{message.content}</div>
              </div>
            ))}
          </div>

          <div className="copilot-composer">
            <textarea
              value={input}
              onChange={event => setInput(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  void sendMessage()
                }
              }}
              placeholder="Ask about this repository..."
              rows={2}
            />
            <button
              className="copilot-send"
              onClick={() => void sendMessage()}
              disabled={isSending || !input.trim()}
              style={{
                background: primaryColor,
              }}
            >
              {isSending ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
