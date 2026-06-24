import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createApiModule } from '@/api'

const topologyApi = createApiModule('/topology')

export const useTopologyStore = defineStore('topology', () => {
  const topologies = ref([])
  const currentTopology = ref(null)
  const loading = ref(false)
  const discovering = ref(false)

  const topologyStats = computed(() => {
    if (!currentTopology.value) return []
    const links = currentTopology.value.link_data || []
    const confirmed = links.filter(l => l.confirmed).length
    const unconfirmed = links.length - confirmed
    return [
      { label: '设备总数', value: currentTopology.value.device_count || 0 },
      { label: '确认链路', value: confirmed },
      { label: '未确认链路', value: unconfirmed },
      { label: '发现时间', value: currentTopology.value.created_at || '—' },
    ]
  })

  async function fetchTopologies() {
    loading.value = true
    try {
      const result = await topologyApi.get('/')
      topologies.value = result.topologies || result
    } finally {
      loading.value = false
    }
  }

  async function fetchTopology(id) {
    loading.value = true
    try {
      currentTopology.value = await topologyApi.get(`/${id}`)
      return currentTopology.value
    } finally {
      loading.value = false
    }
  }

  async function saveTopology(data) {
    loading.value = true
    try {
      const result = await topologyApi.post('/', data)
      await fetchTopologies()
      return result
    } finally {
      loading.value = false
    }
  }

  async function updateTopology(id, data) {
    loading.value = true
    try {
      const result = await topologyApi.put(`/${id}`, data)
      await fetchTopologies()
      return result
    } finally {
      loading.value = false
    }
  }

  async function deleteTopology(id) {
    loading.value = true
    try {
      await topologyApi.delete(`/${id}`)
      await fetchTopologies()
      if (currentTopology.value?.id === id) {
        currentTopology.value = null
      }
    } finally {
      loading.value = false
    }
  }

  async function runDiscovery(params) {
    discovering.value = true
    try {
      return await topologyApi.post('/discover', params)
    } finally {
      discovering.value = false
    }
  }

  async function runSeedDiscovery(params) {
    discovering.value = true
    try {
      return await topologyApi.post('/discover-seed', params)
    } finally {
      discovering.value = false
    }
  }

  async function runSnmpDiscovery(params) {
    discovering.value = true
    try {
      return await topologyApi.post('/snmp-discover', params)
    } finally {
      discovering.value = false
    }
  }

  async function runNetworkScan(params) {
    discovering.value = true
    try {
      return await topologyApi.post('/scan', params)
    } finally {
      discovering.value = false
    }
  }

  function setCurrentTopology(topo) {
    currentTopology.value = topo
  }

  return {
    topologies,
    currentTopology,
    loading,
    discovering,
    topologyStats,
    fetchTopologies,
    fetchTopology,
    saveTopology,
    updateTopology,
    deleteTopology,
    runDiscovery,
    runSeedDiscovery,
    runSnmpDiscovery,
    runNetworkScan,
    setCurrentTopology,
  }
})