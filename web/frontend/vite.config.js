import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

/**
 * Vite 配置
 *
 * 生产环境：base 为 /opsbrain/，通过 Nginx 反向代理
 * 开发环境：Vite proxy /opsbrain/api → 后端 localhost:8000/api
 */
export default defineConfig({
  plugins: [vue()],

  base: process.env.NODE_ENV === 'production' ? '/opsbrain/' : '/',

  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },

  server: {
    port: 3000,
    proxy: {
      '/opsbrain/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/opsbrain\/api/, '/api'),
      },
    },
  },

  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
})
