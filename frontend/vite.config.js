import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Все запросы фронта идут на /api и проксируются на backend:
// в docker compose цель — http://api:8000 (переменная VITE_API_PROXY).
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // Публичные страницы смет для клиентов (в проде этот маршрут возьмёт nginx)
      '/e': {
        target: process.env.VITE_API_PROXY || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
