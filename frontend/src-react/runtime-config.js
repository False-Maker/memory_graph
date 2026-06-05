const LOOPBACK_HOSTNAMES = new Set(['127.0.0.1', 'localhost', '::1', '[::1]'])
const LOCAL_BACKEND_ORIGIN = 'http://127.0.0.1:8000'
const LOCAL_SIDECAR_HEALTH_URL = 'http://127.0.0.1:3001/health'
const LOCAL_FRONTEND_PORT_RANGES = Object.freeze([
  Object.freeze({ start: 4173, end: 4199 }),
  Object.freeze({ start: 5173, end: 5199 }),
])

function readEnv(name) {
  const value = import.meta.env?.[name]
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

export function stripTrailingSlash(value) {
  return value.replace(/\/+$/, '')
}

export function isLoopbackHostname(hostname) {
  return LOOPBACK_HOSTNAMES.has(typeof hostname === 'string' ? hostname.trim().toLowerCase() : '')
}

export function isLocalFrontendWindowLocation(locationLike) {
  if (!locationLike || typeof locationLike !== 'object') {
    return false
  }

  const hostname = typeof locationLike.hostname === 'string' ? locationLike.hostname : ''
  const parsedPort = Number(typeof locationLike.port === 'string' ? locationLike.port : '')

  if (!Number.isInteger(parsedPort)) {
    return false
  }

  return isLoopbackHostname(hostname) && LOCAL_FRONTEND_PORT_RANGES.some(
    (range) => parsedPort >= range.start && parsedPort <= range.end
  )
}

export function resolveRuntimeOrigin(locationLike) {
  if (isLocalFrontendWindowLocation(locationLike)) {
    return LOCAL_BACKEND_ORIGIN
  }

  const origin = typeof locationLike?.origin === 'string' ? locationLike.origin.trim() : ''
  return origin || LOCAL_BACKEND_ORIGIN
}

export function buildDefaultApiBaseUrl(locationLike = typeof window !== 'undefined' ? window.location : null) {
  return `${stripTrailingSlash(resolveRuntimeOrigin(locationLike))}/api/v1`
}

export function buildDefaultBackendHealthUrl(locationLike = typeof window !== 'undefined' ? window.location : null) {
  return `${stripTrailingSlash(resolveRuntimeOrigin(locationLike))}/health`
}

export function buildDefaultSidecarHealthUrl(locationLike = typeof window !== 'undefined' ? window.location : null) {
  if (isLocalFrontendWindowLocation(locationLike)) {
    return LOCAL_SIDECAR_HEALTH_URL
  }

  return `${stripTrailingSlash(resolveRuntimeOrigin(locationLike))}/sidecar/health`
}

export const runtimeConfig = {
  apiBaseUrl: stripTrailingSlash(readEnv('VITE_API_BASE_URL') || buildDefaultApiBaseUrl()),
  backendHealthUrl: readEnv('VITE_BACKEND_HEALTH_URL') || buildDefaultBackendHealthUrl(),
  sidecarHealthUrl: readEnv('VITE_SIDECAR_HEALTH_URL') || buildDefaultSidecarHealthUrl(),
  apiToken: readEnv('VITE_MEMORY_GRAPH_API_TOKEN'),
  isDev: Boolean(import.meta.env?.DEV)
}
