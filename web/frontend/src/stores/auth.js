import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'

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
    user.value = res.user || res
    saveUser(user.value)
    return user.value
  }

  async function login(username, password) {
    const data = await api.post('/auth/login', { username, password })
    localStorage.setItem('opsbrain-token', data.access_token)
    user.value = data.user
    saveUser(data.user)
    return data
  }

  async function setup(username, password, displayName) {
    const data = await api.post('/auth/setup', {
      username,
      password,
      display_name: displayName,
    })
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