import apiClient from './client'

const queryApi = {
  query: (question, params = {}) =>
    apiClient.post('/query', {
      question,
      strategy: params.strategy || 'graphrag',
      retrieval_mode: params.retrieval_mode || 'hybrid',
      top_k: params.top_k || params.topK || 10,
      include_sources: params.includeSources !== false
    }),

  graphRagQuery: (question, params = {}) =>
    apiClient.post('/query', {
      question,
      strategy: 'graphrag',
      retrieval_mode: params.mode || params.retrieval_mode || 'hybrid',
      top_k: params.topK || params.top_k || 10,
      include_sources: params.includeSources !== false
    }),

  graphRagQueryWithMeta: async (question, params = {}) => {
    const response = await apiClient.post('/query', {
      question,
      strategy: 'graphrag',
      retrieval_mode: params.mode || params.retrieval_mode || 'hybrid',
      top_k: params.topK || params.top_k || 10,
      include_sources: params.includeSources !== false
    }, {
      returnRawResponse: true
    })

    return {
      data: response.data,
      runId: response.headers?.['x-query-run-id'] || null,
      sessionId: response.headers?.['x-query-session-id'] || null
    }
  },

  vectorSearch: (query, params = {}) =>
    apiClient.post('/query', {
      question: query,
      strategy: 'graphrag',
      retrieval_mode: 'local',
      top_k: params.topK || 10,
      include_sources: params.includeSources !== false
    }),

  semanticSearch: (query, params = {}) =>
    apiClient.post('/query', {
      question: query,
      strategy: 'graphrag',
      retrieval_mode: 'hybrid',
      top_k: params.topK || 10,
      include_sources: params.includeSources !== false
    }),

  search: (query, params = {}) =>
    apiClient.post('/query', {
      question: query,
      strategy: 'graphrag',
      retrieval_mode: params.mode || 'hybrid',
      top_k: params.topK || 10,
      include_sources: params.includeSources !== false
    }),

  getMemory: (memoryId) =>
    apiClient.get(`/memories/${encodeURIComponent(memoryId)}`),

  listQueryRuns: (params = {}) => {
    const query = new URLSearchParams()
    if (params.limit) query.set('limit', String(params.limit))
    if (params.status) query.set('status', params.status)
    if (params.strategy) query.set('strategy', params.strategy)
    if (params.layerUsed) query.set('layer_used', params.layerUsed)
    if (params.sessionId) query.set('session_id', params.sessionId)
    const suffix = query.toString() ? `?${query}` : ''
    return apiClient.get(`/query/runs${suffix}`)
  },

  getQueryRun: (runId) =>
    apiClient.get(`/query/runs/${encodeURIComponent(runId)}`)
}

export default queryApi
