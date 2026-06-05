import axios from 'axios'
import { runtimeConfig } from '../runtime-config'
import { publishGlobalError } from './errorBus'

const apiClient = axios.create({
  baseURL: runtimeConfig.apiBaseUrl,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json'
  }
})

apiClient.interceptors.request.use(
  (config) => {
    const token = runtimeConfig.apiToken || localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    return config
  },
  (error) => Promise.reject(error)
)

apiClient.interceptors.response.use(
  (response) => {
    if (response.config?.returnRawResponse) {
      return response
    }
    if (response.data?.data) {
      return response.data.data
    }
    return response.data
  },
  (error) => {
    const detail = error?.response?.data?.detail
    const message = error?.response?.data?.message
    const normalizedMessage = detail || message || error?.message || 'Unexpected API error'
    const requestId = error?.response?.headers?.['x-request-id'] || error?.response?.data?.request_id

    publishGlobalError(requestId ? `${normalizedMessage} (request-id: ${requestId})` : normalizedMessage)

    return Promise.reject(error)
  }
)

export default apiClient

export const importApi = {
  importFile: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/data/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  importConversations: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/data/import/conversations', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  scanDirectory: async (directoryPath, extensions = ['.txt', '.md', '.json', '.pdf']) =>
    apiClient.post('/data/scan-directory', {
      directory_path: directoryPath,
      extensions
    }),

  importDirectory: async (directoryPath, extensions = ['.txt', '.md', '.json', '.pdf']) =>
    apiClient.post('/data/import-directory', {
      directory_path: directoryPath,
      extensions
    }),

  retryImportRun: async (runId) =>
    apiClient.post(`/data/import-runs/${encodeURIComponent(runId)}/retry`),

  listImportRuns: async (limit = 10) =>
    apiClient.get(`/data/import-runs?limit=${limit}`)
}

export const dashboardApi = {
  getStats: () => apiClient.get('/graph/stats'),
  getRecentMemories: (limit = 10) => apiClient.get(`/memories?limit=${limit}`),
  getCommunities: (limit = 10) => apiClient.get(`/communities?limit=${limit}`),
  getOperatorSummary: () => apiClient.get('/diagnostics/operator-summary')
}
