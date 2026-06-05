import apiClient from './client.js'
import { buildDiagnosticsQuery } from './diagnostics.helpers.js'

export const diagnosticsApi = {
  getRuntimeDiagnostics: () => apiClient.get('/diagnostics/runtime'),
  getOperatorSummary: () => apiClient.get('/diagnostics/operator-summary'),
  getMcpStatus: () => apiClient.get('/mcp/status'),
  listQueryRuns: (params = {}) => apiClient.get(`/query/runs${buildDiagnosticsQuery({
    limit: params.limit,
    status: params.status,
    strategy: params.strategy,
    layer_used: params.layerUsed,
    session_id: params.sessionId,
  })}`),
  getQueryRun: (runId) => apiClient.get(`/query/runs/${encodeURIComponent(runId)}`)
}
