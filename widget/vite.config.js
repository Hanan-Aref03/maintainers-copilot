import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    lib: {
      entry: 'src/widget.jsx',
      name: 'CopilotWidget',
      formats: ['iife'],
      fileName: () => 'widget.js'
    },
    rollupOptions: {
      external: [],
      output: {
        globals: {}
      }
    }
  }
})