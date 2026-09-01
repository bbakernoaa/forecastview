import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { mkdirSync, writeFileSync } from 'node:fs'

const staticMode = process.env.VITE_STATIC_MODE === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      // Writes the marker that backend/scripts/export_static.py checks
      // before copying a build into the static site.
      name: 'emit-build-info',
      closeBundle() {
        if (!staticMode) return
        mkdirSync('dist/data', { recursive: true })
        writeFileSync(
          'dist/data/build-info.json',
          JSON.stringify({ staticMode: true, builtAt: new Date().toISOString() }),
        )
      },
    },
  ],
  // Base path for deployment (e.g., /gc_wmb/parthab/forecastview/)
  // Set via VITE_BASE_PATH env var, defaults to / for local dev
  base: process.env.VITE_BASE_PATH || '/',
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
