import { createApiModule } from './index'

const taskApi = createApiModule('/tasks')

export const taskApiClient = {
  list: () => taskApi.get('/'),
  get: (id) => taskApi.get(`/${id}`),
  create: (data) => taskApi.post('/', data),
  update: (id, data) => taskApi.put(`/${id}`, data),
  delete: (id) => taskApi.delete(`/${id}`),
  toggle: (id, isEnabled) => taskApi.post(`/${id}/toggle?is_enabled=${isEnabled}`),
  getLogs: (id, limit = 50) => taskApi.get(`/${id}/logs?limit=${limit}`),
  getAllLogs: (limit = 100) => taskApi.get(`/logs/all?limit=${limit}`),
}
