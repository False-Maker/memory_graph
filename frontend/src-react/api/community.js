import apiClient from './client'

const communityApi = {
  detectCommunities: (params = {}) => apiClient.post('/communities/detect', params),
  getCommunities: (params = {}) => apiClient.get('/communities', { params }),
  getCommunity: (id) => apiClient.get(`/communities/${id}`),
  getCommunityDetails: (id, params = {}) => apiClient.get(`/communities/${id}/details`, { params }),
  getCommunityHierarchy: (id, params = {}) => apiClient.get(`/communities/${id}/hierarchy`, { params }),
  getFullHierarchy: (params = {}) => apiClient.get('/communities/hierarchy', { params }),
  summarizeCommunity: (id, params = {}) => apiClient.post(`/communities/${id}/summarize`, params),
  getCommunityStats: (id) => apiClient.get(`/communities/${id}/stats`),
  searchCommunities: (query, params = {}) => apiClient.get('/communities/search', { params: { ...params, query } }),
  getCommunityEntities: (id, params = {}) => apiClient.get(`/communities/${id}/entities`, { params }),
  getCommunityRelationships: (id, params = {}) => apiClient.get(`/communities/${id}/relationships`, { params }),
  getCommunitiesByLevel: (level, params = {}) => apiClient.get('/communities/by-level', { params: { ...params, level } }),
  getParentCommunity: (id) => apiClient.get(`/communities/${id}/parent`),
  getChildCommunities: (id, params = {}) => apiClient.get(`/communities/${id}/children`, { params }),
  getCommunityAncestors: (id, params = {}) => apiClient.get(`/communities/${id}/ancestors`, { params }),
  getCommunityDescendants: (id, params = {}) => apiClient.get(`/communities/${id}/descendants`, { params })
}

export default communityApi
