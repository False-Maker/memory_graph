import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { runtimeConfig } from '../runtime-config'
import {
  DEFAULT_STARTUP_SERVICE_STATE,
  buildBackendDiagnosticsUnavailableState,
  buildBackendStartupState,
  buildDownStartupServiceState,
  buildSidecarStartupState,
  buildStartupAlertState,
  normalizeProbeError,
} from './startup-runtime-diagnostics'
import './StartupPage.css'

const PROBE_TIMEOUT_MS = 5000
const BACKEND_HEALTH_URL = runtimeConfig.backendHealthUrl
const SIDECAR_HEALTH_URL = runtimeConfig.sidecarHealthUrl
const BACKEND_DIAGNOSTICS_URL = `${runtimeConfig.apiBaseUrl}/diagnostics/runtime`

const SERVICE_LABELS = {
  backend: 'Backend API',
  sidecar: 'Sidecar API'
}

const STATUS_LABELS = {
  unknown: 'UNKNOWN',
  checking: 'CHECKING',
  up: 'UP',
  down: 'DOWN'
}

const STATUS_HINTS = {
  unknown: '尚未探测，请点击“检查服务状态”。',
  checking: '正在探测服务健康状态，请稍候。',
  up: '基础服务可达，下面的运行诊断会继续说明当前是否可信。',
  down: '服务不可达，请按下方运维指引检查后重试。'
}

async function probeHealth(url) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)

  try {
    const response = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      headers: { Accept: 'application/json' }
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    return await response.json()
  } finally {
    clearTimeout(timer)
  }
}

async function checkSidecarService() {
  const checkedAt = new Date().toISOString()

  try {
    return buildSidecarStartupState(await probeHealth(SIDECAR_HEALTH_URL), checkedAt)
  } catch (error) {
    return buildDownStartupServiceState(normalizeProbeError(error), checkedAt)
  }
}

async function checkBackendService() {
  const checkedAt = new Date().toISOString()

  try {
    const healthPayload = await probeHealth(BACKEND_HEALTH_URL)
    if (healthPayload?.status !== 'healthy') {
      return buildDownStartupServiceState(`Unexpected payload: ${JSON.stringify(healthPayload)}`, checkedAt)
    }

    try {
      const diagnosticsPayload = await probeHealth(BACKEND_DIAGNOSTICS_URL)
      return buildBackendStartupState(healthPayload, diagnosticsPayload, checkedAt)
    } catch (diagnosticsError) {
      return buildBackendDiagnosticsUnavailableState(diagnosticsError, checkedAt)
    }
  } catch (error) {
    return buildDownStartupServiceState(normalizeProbeError(error), checkedAt)
  }
}

function ServiceStatusCard({ serviceKey, state }) {
  const label = SERVICE_LABELS[serviceKey]
  const statusText = STATUS_LABELS[state.status]

  return (
    <article className="startup-service-card" aria-label={`${label} status card`}>
      <div className="startup-service-header">
        <h2>{label}</h2>
        <span className={`startup-status-badge startup-status-badge--${state.status}`}>{statusText}</span>
      </div>

      <p className="startup-status-hint">{STATUS_HINTS[state.status]}</p>
      <p className="startup-status-detail">细节：{state.detail || '暂无'}</p>
      {serviceKey === 'backend' && state.runtimeTone !== 'unknown' ? (
        <div className={`startup-runtime-panel startup-runtime-panel--${state.runtimeTone}`}>
          <div className="startup-runtime-head">
            <span className={`startup-runtime-badge startup-runtime-badge--${state.runtimeTone}`}>
              {state.runtimeTone === 'healthy' ? 'Runtime OK' : 'Runtime ATTN'}
            </span>
            <span className="startup-runtime-title">运行诊断</span>
          </div>
          <p className="startup-runtime-message">{state.runtimeMessage || '暂无'}</p>
          {state.runtimeDetail ? (
            <p className="startup-runtime-detail">{state.runtimeDetail}</p>
          ) : null}
        </div>
      ) : null}
      <p className="startup-status-time">最近探测：{state.checkedAt ? new Date(state.checkedAt).toLocaleString('zh-CN') : '未探测'}</p>
    </article>
  )
}

export default function StartupPage() {
  const [checking, setChecking] = useState(false)
  const [lastCheckedAt, setLastCheckedAt] = useState(null)
  const [services, setServices] = useState({
    backend: { ...DEFAULT_STARTUP_SERVICE_STATE },
    sidecar: { ...DEFAULT_STARTUP_SERVICE_STATE }
  })

  const hasFailures = useMemo(
    () => services.backend.status === 'down' || services.sidecar.status === 'down',
    [services.backend.status, services.sidecar.status]
  )

  const startupAlert = useMemo(
    () => buildStartupAlertState(services),
    [services]
  )

  async function handleCheckServices() {
    setChecking(true)
    setServices((current) => ({
      backend: { ...current.backend, status: 'checking' },
      sidecar: { ...current.sidecar, status: 'checking' }
    }))

    const [backend, sidecar] = await Promise.all([
      checkBackendService(),
      checkSidecarService()
    ])

    setServices({ backend, sidecar })
    setLastCheckedAt(new Date().toISOString())
    setChecking(false)
  }

  return (
    <section className="startup-page" aria-label="Startup page">
      <header className="startup-page-header">
        <h1>服务启动检查</h1>
        <p className="startup-subtitle">运维辅助页：仅提供健康探测与诊断指引，不承担默认业务入口。</p>
      </header>

      <div className="startup-primary-actions" aria-label="Core entry shortcuts">
        <Link className="startup-primary-link" to="/inbox">进入 Inbox</Link>
        <Link className="startup-primary-link startup-primary-link--ghost" to="/search">进入 Search</Link>
      </div>

      <div className="startup-toolbar">
        <button type="button" className="btn-check-services" onClick={handleCheckServices} disabled={checking}>
          {checking ? '检查中...' : '检查服务状态'}
        </button>
        <p className="startup-toolbar-meta">上次检查：{lastCheckedAt ? new Date(lastCheckedAt).toLocaleString('zh-CN') : '尚未检查'}</p>
      </div>

      {hasFailures ? (
        <div className="startup-alert startup-alert--error" role="alert">
          {startupAlert?.message}
        </div>
      ) : null}

      {!hasFailures && startupAlert?.tone === 'warning' ? (
        <div className="startup-alert startup-alert--warning" role="status">
          {startupAlert.message}
        </div>
      ) : null}

      {!hasFailures && startupAlert?.tone === 'success' ? (
        <div className="startup-alert startup-alert--success" role="status">
          {startupAlert.message}
        </div>
      ) : null}

      <div className="startup-services-grid">
        <ServiceStatusCard serviceKey="backend" state={services.backend} />
        <ServiceStatusCard serviceKey="sidecar" state={services.sidecar} />
      </div>

      <section className="startup-guidance" aria-label="Operator guidance">
        <h2>运维指引</h2>
        <ol>
          <li>确认 Python API 服务可访问 <code>{BACKEND_HEALTH_URL}</code>。</li>
          <li>确认 backend 运行诊断可访问 <code>{BACKEND_DIAGNOSTICS_URL}</code>，并关注 provider / store / recent failures。</li>
          <li>确认 Sidecar 服务可访问 <code>{SIDECAR_HEALTH_URL}</code>。</li>
          <li>若基础探测通过但 runtime 仍有告警，请优先到 Settings 查看当前 provider 和运行诊断详情。</li>
        </ol>
      </section>
    </section>
  )
}
