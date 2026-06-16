import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // If you set VITE_API_BASE=/api, point VITE_PROXY_TARGET at the Python backend
  // so dev requests to /api are proxied there (avoids CORS during local dev).
  const proxyTarget = env.VITE_PROXY_TARGET // e.g. http://localhost:8000

  return {
    plugins: [react()],
    server: {
      port: 5173,
      open: true,
      proxy: proxyTarget
        ? { '/api': { target: proxyTarget, changeOrigin: true } }
        : undefined,
    },
  }
})
