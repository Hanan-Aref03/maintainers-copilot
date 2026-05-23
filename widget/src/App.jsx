import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

const DEFAULT_API_URL = 'http://localhost:8010'
const DEFAULT_WIDGET_ID = 'widget123'
const DEFAULT_THEME = {
  primary_color: '#0f766e',
  position: 'bottom-right',
}

const DEFAULT_QUICK_PROMPTS = [
  {
    label: 'Summarize',
    prompt: 'Summarize this thread.',
  },
  {
    label: 'Classify',
    prompt: 'Suggest the best label.',
  },
  {
    label: 'Memory',
    prompt: 'Capture a durable note.',
  },
]

function sanitizeMessage(text) {
  return String(text ?? '').replace(/\s+/g, ' ').trim()
}

function normalizePrompt(item, index) {
  const label = sanitizeMessage(item?.label ?? item?.title ?? `Prompt ${index + 1}`)
  const prompt = sanitizeMessage(item?.prompt ?? item?.text ?? '')

  if (!prompt) {
    return null
  }

  return {
    label: label || `Prompt ${index + 1}`,
    prompt,
  }
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

  const quickPrompts = Array.isArray(runtimeConfig.quickPrompts) && runtimeConfig.quickPrompts.length > 0
    ? runtimeConfig.quickPrompts
        .map((item, index) => normalizePrompt(item, index))
        .filter(Boolean)
    : DEFAULT_QUICK_PROMPTS

  return {
    apiUrl: runtimeConfig.apiUrl ?? scriptOrigin ?? DEFAULT_API_URL,
    widgetId: runtimeConfig.widgetId ?? scriptTag?.dataset?.widgetId ?? DEFAULT_WIDGET_ID,
    theme: {
      ...DEFAULT_THEME,
      ...(runtimeConfig.theme ?? {}),
      primary_color:
        runtimeConfig.theme?.primary_color ??
        runtimeConfig.theme?.primaryColor ??
        DEFAULT_THEME.primary_color,
      position: runtimeConfig.theme?.position ?? DEFAULT_THEME.position,
    },
    greeting: runtimeConfig.greeting ?? 'How can I help?',
    enabledTools: Array.isArray(runtimeConfig.enabledTools)
      ? runtimeConfig.enabledTools
      : ['classify', 'rag', 'memory'],
    quickPrompts,
  }
}

const widgetConfig = readWidgetConfig()

function buildAssistantMeta(data) {
  const retrievedDocIds = Array.isArray(data?.retrieved_doc_ids)
    ? data.retrieved_doc_ids.filter(Boolean).map(value => String(value))
    : []

  return {
    provider: String(data?.llm_provider ?? 'local').toLowerCase(),
    usedFallback: Boolean(data?.used_fallback),
    retrievedDocIds,
  }
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
    const height = open ? Math.min(760, 392 + Math.min(messages.length, 6) * 52) : 92
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

  const sendMessage = async overrideMessage => {
    const prompt = sanitizeMessage(overrideMessage ?? input)
    if (!prompt || isSending) return

    setOpen(true)
    setIsSending(true)
    setMessages(prev => [...prev, { role: 'user', content: prompt }])

    if (!overrideMessage) {
      setInput('')
    }

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
          meta: buildAssistantMeta(data),
        },
      ])
    } catch {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I could not reach the assistant right now.',
          meta: {
            provider: 'local',
            usedFallback: true,
            retrievedDocIds: [],
          },
        },
      ])
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div
      className="copilot-widget"
      style={{
        ...positionStyle,
        alignItems,
        '--copilot-accent': primaryColor,
      }}
    >
      <button
        type="button"
        className="copilot-launcher"
        onClick={() => setOpen(current => !current)}
      >
        <span className="copilot-launcher-dot" />
        <span>{open ? 'Close' : 'Open Copilot'}</span>
      </button>

      {open ? (
        <div className="copilot-panel">
          <div className="copilot-header">
            <div>
              <div className="copilot-eyebrow">Maintainers' Copilot</div>
              <div className="copilot-title">Fast triage and repo memory</div>
              <div className="copilot-subtitle">Concise answers, sources, and clear fallback status.</div>
            </div>
            <button
              type="button"
              className="copilot-close"
              onClick={() => setOpen(false)}
              aria-label="Close widget"
            >
              Close
            </button>
          </div>

          <div className="copilot-toolbar">
            <div className="copilot-status-pill">
              <span className="copilot-status-dot" />
              Live
            </div>
            {widgetConfig.enabledTools.slice(0, 3).map(tool => (
              <span key={tool} className="copilot-chip">
                {tool}
              </span>
            ))}
          </div>

          <div className="copilot-quick-actions">
            {widgetConfig.quickPrompts.map(prompt => (
              <button
                key={prompt.label}
                type="button"
                className="copilot-quick-button"
                onClick={() => void sendMessage(prompt.prompt)}
                disabled={isSending}
                title={prompt.prompt}
              >
                <span className="copilot-quick-label">{prompt.label}</span>
                <span className="copilot-quick-copy">{prompt.prompt}</span>
              </button>
            ))}
          </div>

          <div className="copilot-messages" ref={messageListRef}>
            {messages.map((message, index) => {
              const isAssistant = message.role === 'assistant'
              const meta = message.meta ?? null

              return (
                <div
                  key={`${message.role}-${index}`}
                  className={`copilot-message copilot-message--${message.role}`}
                >
                  <div className="copilot-message-role">
                    {isAssistant ? 'Copilot' : 'You'}
                  </div>
                  <div className="copilot-message-bubble">{message.content}</div>
                  {meta ? (
                    <div className="copilot-message-meta">
                      <span className="copilot-message-pill">{meta.provider}</span>
                      {meta.usedFallback ? (
                        <span className="copilot-message-pill copilot-message-pill--warn">
                          fallback
                        </span>
                      ) : null}
                      <span className="copilot-message-pill">
                        {meta.retrievedDocIds.length > 0
                          ? `${meta.retrievedDocIds.length} source${
                              meta.retrievedDocIds.length === 1 ? '' : 's'
                            }`
                          : 'No sources'}
                      </span>
                    </div>
                  ) : null}
                </div>
              )
            })}
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
              placeholder="Ask about an issue, thread, or widget setup..."
              rows={3}
            />
            <div className="copilot-composer-row">
              <div className="copilot-hint">Enter to send | Shift+Enter for newline</div>
              <button
                type="button"
                className="copilot-send"
                onClick={() => void sendMessage()}
                disabled={isSending || !input.trim()}
              >
                {isSending ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>

          <div className="copilot-footer">
            API <code>{widgetConfig.apiUrl}</code>
          </div>
        </div>
      ) : null}
    </div>
  )
}
