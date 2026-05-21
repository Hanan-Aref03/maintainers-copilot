import { createRoot } from 'react-dom/client'
import App from './App'

// Auto-inject widget into host page
const container = document.createElement('div')
container.id = 'copilot-widget-root'
document.body.appendChild(container)
createRoot(container).render(<App />)
