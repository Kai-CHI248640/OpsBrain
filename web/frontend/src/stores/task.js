import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { taskApiClient } from '@/api/task'

export const useTaskStore = defineStore('task', () => {
  const tasks = ref([])
  const logs = ref([])
  const loading = ref(false)

  const enabledTasks = computed(() => tasks.value.filter(t => t.is_enabled))

  async function fetchTasks() {
    loading.value = true
    try {
      tasks.value = await taskApiClient.list()
    } finally {
      loading.value = false
    }
  }

  async function fetchTask(id) {
    return await taskApiClient.get(id)
  }

  async function createTask(data) {
    const task = await taskApiClient.create(data)
    tasks.value.unshift(task)
    return task
  }

  async function updateTask(id, data) {
    const task = await taskApiClient.update(id, data)
    const index = tasks.value.findIndex(t => t.id === id)
    if (index !== -1) {
      tasks.value[index] = task
    }
    return task
  }

  async function deleteTask(id) {
    await taskApiClient.delete(id)
    tasks.value = tasks.value.filter(t => t.id !== id)
  }

  async function toggleTask(id, isEnabled) {
    const task = await taskApiClient.toggle(id, isEnabled)
    const index = tasks.value.findIndex(t => t.id === id)
    if (index !== -1) {
      tasks.value[index] = task
    }
    return task
  }

  async function fetchLogs(taskId) {
    if (taskId) {
      logs.value = await taskApiClient.getLogs(taskId)
    } else {
      logs.value = await taskApiClient.getAllLogs()
    }
    return logs.value
  }

  return {
    tasks,
    logs,
    loading,
    enabledTasks,
    fetchTasks,
    fetchTask,
    createTask,
    updateTask,
    deleteTask,
    toggleTask,
    fetchLogs,
  }
})
