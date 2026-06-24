import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createApiModule } from '@/api'

const settingsApi = createApiModule('/settings')
const apiKeysApi = createApiModule('/apis')

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref([])
  const apiKeys = ref([])
  const loading = ref(false)

  async function fetchSettings() {
    loading.value = true
    try {
      const result = await settingsApi.get('/')
      settings.value = result.settings || result
    } finally {
      loading.value = false
    }
  }

  async function updateSetting(key, value, category = 'general', description = '') {
    loading.value = true
    try {
      return await settingsApi.post('/update', { key, value, category, description })
    } finally {
      loading.value = false
    }
  }

  async function fetchApiKeys() {
    loading.value = true
    try {
      const result = await apiKeysApi.get('/')
      apiKeys.value = result.api_keys || result
    } finally {
      loading.value = false
    }
  }

  async function createApiKey(data) {
    loading.value = true
    try {
      const result = await apiKeysApi.post('/', data)
      await fetchApiKeys()
      return result
    } finally {
      loading.value = false
    }
  }

  async function updateApiKey(id, data) {
    loading.value = true
    try {
      const result = await apiKeysApi.put(`/${id}`, data)
      await fetchApiKeys()
      return result
    } finally {
      loading.value = false
    }
  }

  async function deleteApiKey(id) {
    loading.value = true
    try {
      await apiKeysApi.delete(`/${id}`)
      await fetchApiKeys()
    } finally {
      loading.value = false
    }
  }

  function getSetting(key, defaultValue = '') {
    const setting = settings.value.find(s => s.key === key)
    return setting ? setting.value : defaultValue
  }

  return {
    settings,
    apiKeys,
    loading,
    fetchSettings,
    updateSetting,
    fetchApiKeys,
    createApiKey,
    updateApiKey,
    deleteApiKey,
    getSetting,
  }
})