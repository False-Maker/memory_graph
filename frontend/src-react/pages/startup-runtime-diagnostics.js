import {
  buildRuntimeDiagnosticsSummary,
  normalizeRuntimeDiagnostics,
} from './settings-runtime-diagnostics.js'

export const DEFAULT_STARTUP_SERVICE_STATE = Object.freeze({
  status: 'unknown',
  detail: '',
  checkedAt: null,
  runtimeTone: 'unknown',
  runtimeMessage: '',
  runtimeDetail: '',
})

function stringifyPayload(payload) {
  try {
    return JSON.stringify(payload)
  } catch {
    return String(payload)
  }
}

export function normalizeProbeError(error) {
  if (!error) return 'unknown error'
  return error.message || String(error)
}

export function buildDownStartupServiceState(detail, checkedAt) {
  return {
    ...DEFAULT_STARTUP_SERVICE_STATE,
    status: 'down',
    detail,
    checkedAt,
  }
}

export function buildSidecarStartupState(payload, checkedAt) {
  if (payload?.status !== 'UP') {
    return buildDownStartupServiceState(`Unexpected payload: ${stringifyPayload(payload)}`, checkedAt)
  }

  return {
    ...DEFAULT_STARTUP_SERVICE_STATE,
    status: 'up',
    detail: 'Sidecar health probe succeeded',
    checkedAt,
  }
}

export function buildBackendDiagnosticsUnavailableState(error, checkedAt) {
  return {
    ...DEFAULT_STARTUP_SERVICE_STATE,
    status: 'up',
    detail: '基础健康探测通过，但运行诊断读取失败。',
    checkedAt,
    runtimeTone: 'warning',
    runtimeMessage: '无法确认 backend 运行态是否可信。',
    runtimeDetail: normalizeProbeError(error),
  }
}

export function buildBackendStartupState(healthPayload, diagnosticsPayload, checkedAt) {
  if (healthPayload?.status !== 'healthy') {
    return buildDownStartupServiceState(`Unexpected payload: ${stringifyPayload(healthPayload)}`, checkedAt)
  }

  const diagnosticsSummary = buildRuntimeDiagnosticsSummary(diagnosticsPayload)
  const normalizedDiagnostics = normalizeRuntimeDiagnostics(diagnosticsPayload)
  const runtimeTone = diagnosticsSummary.tone === 'success' ? 'healthy' : 'warning'

  return {
    ...DEFAULT_STARTUP_SERVICE_STATE,
    status: 'up',
    detail: runtimeTone === 'healthy'
      ? '基础健康探测与运行诊断通过。'
      : '基础健康探测通过，但运行诊断仍需处理。',
    checkedAt,
    runtimeTone,
    runtimeMessage: diagnosticsSummary.message,
    runtimeDetail: diagnosticsSummary.detail || (
      runtimeTone === 'healthy'
        ? `最近诊断时间：${normalizedDiagnostics.generated_at || 'unknown'}`
        : ''
    ),
  }
}

export function buildStartupAlertState(services) {
  const backend = services?.backend || DEFAULT_STARTUP_SERVICE_STATE
  const sidecar = services?.sidecar || DEFAULT_STARTUP_SERVICE_STATE

  if (backend.status === 'down' || sidecar.status === 'down') {
    return {
      tone: 'error',
      message: '检测到基础服务不可达。请先确认 backend 与 sidecar 已启动，再刷新本页重新检查。',
    }
  }

  if (backend.status === 'up' && sidecar.status === 'up' && backend.runtimeTone === 'warning') {
    return {
      tone: 'warning',
      message: '基础服务可达，但 backend 运行诊断仍有告警。请先到 Settings 检查当前 provider、存储和最近失败记录。',
    }
  }

  if (backend.status === 'up' && sidecar.status === 'up') {
    return {
      tone: 'success',
      message: '所有基础服务探测通过，当前启动状态可继续进入功能页面。',
    }
  }

  return null
}
