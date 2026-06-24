import axios from 'axios'

function getApiBase() {
  const path = window.location.pathname.replace(/\/+$/, '')
  const parts = path.split('/').filter(Boolean)
  const prefix = parts.length > 0 ? '/' + parts[0] : ''
  return `${prefix}/api/v1`
}

const api = axios.create({
  baseURL: getApiBase(),
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('opsbrain-token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => {
    if (res.data && typeof res.data === 'object') {
      if ('ok' in res.data && !res.data.ok) {
        return Promise.reject(new Error(res.data.error || '操作失败'))
      }
      return res.data.data !== undefined ? res.data.data : res.data
    }
    return res
  },
  (err) => {
    if (err.response?.status === 401) {
      const currentPath = window.location.hash || ''
      if (!currentPath.includes('/login') && !currentPath.includes('/setup')) {
        localStorage.removeItem('opsbrain-token')
        localStorage.removeItem('opsbrain-user')
        window.location.hash = '#/login'
      }
    }
    const message = err.response?.data?.error || err.response?.data?.detail || err.message
    return Promise.reject(new Error(message))
  },
)

export function createApiModule(basePath) {
  return {
    async get(url, params) {
      return api.get(`${basePath}${url}`, { params })
    },
    async post(url, data) {
      return api.post(`${basePath}${url}`, data)
    },
    async put(url, data) {
      return api.put(`${basePath}${url}`, data)
    },
    async delete(url) {
      return api.delete(`${basePath}${url}`)
    },
  }
}

export { api }
export default api