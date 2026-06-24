import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createApiModule } from '@/api'

const workflowApi = createApiModule('/workflow')

export const useWorkflowStore = defineStore('workflow', () => {
  const workflows = ref([])
  const currentWorkflow = ref(null)
  const executions = ref([])
  const loading = ref(false)
  const executing = ref(false)

  async function fetchWorkflows() {
    loading.value = true
    try {
      const result = await workflowApi.get('/')
      workflows.value = result.workflows || result
    } finally {
      loading.value = false
    }
  }

  async function fetchWorkflow(id) {
    loading.value = true
    try {
      currentWorkflow.value = await workflowApi.get(`/${id}`)
      return currentWorkflow.value
    } finally {
      loading.value = false
    }
  }

  async function createWorkflow(data) {
    loading.value = true
    try {
      const result = await workflowApi.post('/', data)
      await fetchWorkflows()
      return result
    } finally {
      loading.value = false
    }
  }

  async function updateWorkflow(id, data) {
    loading.value = true
    try {
      const result = await workflowApi.put(`/${id}`, data)
      await fetchWorkflows()
      return result
    } finally {
      loading.value = false
    }
  }

  async function deleteWorkflow(id) {
    loading.value = true
    try {
      await workflowApi.delete(`/${id}`)
      await fetchWorkflows()
      if (currentWorkflow.value?.id === id) {
        currentWorkflow.value = null
      }
    } finally {
      loading.value = false
    }
  }

  async function executeWorkflow(id, params = {}) {
    executing.value = true
    try {
      return await workflowApi.post(`/${id}/execute`, params)
    } finally {
      executing.value = false
    }
  }

  async function fetchExecutions(workflowId) {
    loading.value = true
    try {
      const result = await workflowApi.get(`/${workflowId}/executions`)
      executions.value = result.executions || result
      return executions.value
    } finally {
      loading.value = false
    }
  }

  async function fetchExecution(id) {
    try {
      return await workflowApi.get(`/execution/${id}`)
    } finally {
      loading.value = false
    }
  }

  function setCurrentWorkflow(workflow) {
    currentWorkflow.value = workflow
  }

  return {
    workflows,
    currentWorkflow,
    executions,
    loading,
    executing,
    fetchWorkflows,
    fetchWorkflow,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    executeWorkflow,
    fetchExecutions,
    fetchExecution,
    setCurrentWorkflow,
  }
})