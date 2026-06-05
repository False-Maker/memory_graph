export const DIAGNOSTICS_TABS = ['overview', 'query-runs', 'runtime', 'mcp', 'failures']

export function normalizeDiagnosticsTab(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return DIAGNOSTICS_TABS.includes(normalized) ? normalized : 'overview'
}

export function buildDiagnosticsHref({ tab = 'overview', runId = null } = {}) {
  const search = new URLSearchParams()
  search.set('tab', normalizeDiagnosticsTab(tab))
  if (runId) {
    search.set('run_id', String(runId))
  }
  return `/diagnostics?${search.toString()}`
}

export function normalizeOperatorSummary(payload) {
  const normalized = payload && typeof payload === 'object' ? payload : {}
  return {
    status: typeof normalized.status === 'string' ? normalized.status : 'unknown',
    generated_at: normalized.generated_at || null,
    runtime: normalized.runtime && typeof normalized.runtime === 'object' ? normalized.runtime : {},
    query_runs: normalized.query_runs && typeof normalized.query_runs === 'object' ? normalized.query_runs : {},
    sync_sources: normalized.sync_sources && typeof normalized.sync_sources === 'object' ? normalized.sync_sources : {},
    mcp: normalized.mcp && typeof normalized.mcp === 'object' ? normalized.mcp : {},
    collectors: normalized.collectors && typeof normalized.collectors === 'object' ? normalized.collectors : {},
  }
}

export function normalizeMcpStatus(payload) {
  const normalized = payload && typeof payload === 'object' ? payload : {}
  return {
    configured: Boolean(normalized.configured),
    transport: typeof normalized.transport === 'string' ? normalized.transport : 'unknown',
    reachable: typeof normalized.reachable === 'boolean' ? normalized.reachable : null,
    auth_enabled: Boolean(normalized.auth_enabled),
    tools_count: Number.isFinite(Number(normalized.tools_count)) ? Number(normalized.tools_count) : 0,
    core_tools: Array.isArray(normalized.core_tools) ? normalized.core_tools : [],
    missing_core_tools: Array.isArray(normalized.missing_core_tools) ? normalized.missing_core_tools : [],
    detail: typeof normalized.detail === 'string' ? normalized.detail : null,
    base_url: typeof normalized.base_url === 'string' ? normalized.base_url : null,
  }
}

export function normalizeQueryRunsResponse(payload) {
  const normalized = payload && typeof payload === 'object' ? payload : {}
  return {
    runs: Array.isArray(normalized.runs) ? normalized.runs : [],
    total: Number.isFinite(Number(normalized.total)) ? Number(normalized.total) : 0,
  }
}

export function normalizeQueryRunDetail(payload) {
  return payload && typeof payload === 'object' ? payload : null
}

export function normalizeRecentFailures(payload) {
  const failures = Array.isArray(payload?.recent_failures) ? payload.recent_failures : []
  return failures.map((item) => ({
    component: item?.component || 'unknown',
    detail: item?.detail || '',
    category: item?.category || 'unknown',
    severity: item?.severity || 'warning',
    suggested_action: item?.suggested_action || '',
    count: Number.isFinite(Number(item?.count)) ? Number(item.count) : 0,
    first_seen_at: item?.first_seen_at || null,
    last_seen_at: item?.last_seen_at || null,
  }))
}

export function buildQueryRunsRequestParams(filters = {}) {
  return {
    limit: filters.limit || 20,
    status: filters.status || '',
    strategy: filters.strategy || '',
    layerUsed: filters.layerUsed || '',
    sessionId: filters.sessionId || '',
  }
}
