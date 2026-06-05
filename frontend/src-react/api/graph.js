import apiClient from './client'

const graphApi = {
  getStats: () => apiClient.get('/graph/stats'),
  getEntities: (params = {}) => apiClient.get('/graph/entities', { params }),
  getEntity: (id) => apiClient.get(`/graph/entities/${id}`),
  getRelationships: (params = {}) => apiClient.get('/graph/relationships', { params }),
  getNeighbors: (entityId, depth = 1, params = {}) =>
    apiClient.get(`/graph/entities/${entityId}/neighbors`, { params: { ...params, depth } })
}

export default graphApi
