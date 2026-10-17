import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // send API calls to the Flask server, so the browser sees one origin
    proxy: {
      '/api': 'http://127.0.0.1:5000',
    },
  },
})