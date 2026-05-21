import { createRoot } from 'react-dom/client'
import App from './App'

const existingRoot = document.getElementById('copilot-widget-root')
const container = existingRoot ?? document.createElement('div')

if (!existingRoot) {
  container.id = 'copilot-widget-root'
  document.body.appendChild(container)
}

createRoot(container).render(<App />)
