/**
 * OpsBrain Web — API Client
 *
 * 动态计算 API Base URL：
 *   - 生产: 当前路径前缀 + /api/v1 (如 /opsbrain/api/v1)
 *   - 开发: vite proxy → /api/v1
 *
 * 自动附加 JWT 认证、处理 401 跳登录。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

// ── 动态 API Base ─────────────────────────────────────────────────────────
function getApiBase() {
  const path = window.location.pathname.replace(/\/+$/, '')
  // 取第一个路径段作为部署前缀（如 /opsbrain），开发环境取空
  const parts = path.split('/').filter(Boolean)
  const prefix = parts.length > 0 ? '/' + parts[0] : ''
  return `${prefix}/api/v1`
}

const api = axios.create({
  baseURL: getApiBase(),
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── 请求拦截器：JWT ────────────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('opsbrain-token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── 响应拦截器：401 → 登录 ────────────────────────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('opsbrain-token')
      localStorage.removeItem('opsbrain-user')
      window.location.hash = '#/login'
    }
    return Promise.reject(err)
  },
)

// ── Auth Store ───────────────────────────────────────────────────────────

export const useAuthStore = defineStore('auth', () => {
  const user = ref(loadUser())
  const loading = ref(false)

  function loadUser() {
    try {
      const raw = localStorage.getItem('opsbrain-user')
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }

  function saveUser(u) {
    if (u) {
      localStorage.setItem('opsbrain-user', JSON.stringify(u))
    } else {
      localStorage.removeItem('opsbrain-user')
    }
  }

  async function fetchUser() {
    const res = await api.get('/auth/me')
    user.value = res.data
    saveUser(res.data)
    return res.data
  }

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    const data = res.data
    localStorage.setItem('opsbrain-token', data.access_token)
    user.value = data.user
    saveUser(data.user)
    return data
  }

  async function setup(username, password, displayName) {
    const res = await api.post('/auth/setup', {
      username,
      password,
      display_name: displayName,
    })
    const data = res.data
    localStorage.setItem('opsbrain-token', data.access_token)
    user.value = data.user
    saveUser(data.user)
    return data
  }

  function logout() {
    user.value = null
    localStorage.removeItem('opsbrain-token')
    localStorage.removeItem('opsbrain-user')
  }

  return { user, loading, fetchUser, login, setup, logout }
})

export { api }
