import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// MatSelect 前端构建配置（契约 §3：dev 5173，/api 代理到后端 8100）
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1600,
  },
})
