import { useState, useEffect } from 'react'

export default function App() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [token, setToken] = useState(null)

  useEffect(() => {
    // Retrieve widget ID from script tag attribute
    const scriptTag = document.querySelector('script[data-widget-id]')
    const widgetId = scriptTag?.dataset.widgetId
    // You would then fetch config from backend and authenticate (simplified)
    // For demo, we mock login
    setToken('mock-token')
  }, [])

  const sendMessage = async () => {
    if (!input.trim()) return
    const userMsg = { role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    // Call your API
    const res = await fetch('http://localhost:8000/chat/?message=' + encodeURIComponent(input) + '&thread_id=widget123', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await res.json()
    setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
  }

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 9999 }}>
      <button onClick={() => setOpen(!open)} style={{ background: '#3b82f6', color: 'white', border: 'none', borderRadius: 50, padding: '12px 20px', cursor: 'pointer' }}>
        💬
      </button>
      {open && (
        <div style={{ width: 350, height: 500, background: 'white', border: '1px solid #ccc', borderRadius: 12, marginTop: 10, display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: 12, background: '#3b82f6', color: 'white', borderTopLeftRadius: 12, borderTopRightRadius: 12 }}>Maintainer's Copilot</div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ marginBottom: 8, textAlign: m.role === 'user' ? 'right' : 'left' }}>
                <strong>{m.role === 'user' ? 'You' : 'Bot'}:</strong> {m.content}
              </div>
            ))}
          </div>
          <div style={{ padding: 12, borderTop: '1px solid #eee', display: 'flex' }}>
            <input value={input} onChange={e => setInput(e.target.value)} onKeyPress={e => e.key === 'Enter' && sendMessage()} style={{ flex: 1, padding: 8, borderRadius: 20, border: '1px solid #ccc' }} />
            <button onClick={sendMessage} style={{ marginLeft: 8, background: '#3b82f6', color: 'white', border: 'none', borderRadius: 20, padding: '8px 16px' }}>Send</button>
          </div>
        </div>
      )}
    </div>
  )
}