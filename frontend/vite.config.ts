import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, the Vite server proxies API and OAuth routes to FastAPI so everything is
// same-origin (cookies and OAuth callbacks behave like production).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
    },
  },
})
