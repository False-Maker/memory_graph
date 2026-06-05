import path from 'node:path'

export const OFFICIAL_COLLECTOR_SMOKE_CASES = Object.freeze([
  Object.freeze({
    collectorType: 'windsurf',
    label: 'official-windsurf',
    supportTier: 'official',
  }),
  Object.freeze({
    collectorType: 'claude_code',
    label: 'official-claude-code',
    supportTier: 'official',
  }),
  Object.freeze({
    collectorType: 'aider',
    label: 'official-aider',
    supportTier: 'official',
  }),
])

function normalizeOptionalValue(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

export function getOfficialCollectorSmokeCase(collectorType) {
  return OFFICIAL_COLLECTOR_SMOKE_CASES.find((item) => item.collectorType === collectorType) || null
}

export function getOfficialCollectorMatrixEvidencePaths(evidenceDir) {
  return {
    summary: path.join(evidenceDir, 'task-61-official-collector-matrix-summary.txt'),
    json: path.join(evidenceDir, 'task-61-official-collector-matrix-summary.json'),
    backendLog: path.join(evidenceDir, 'task-61-official-collector-matrix-backend.log'),
    http: path.join(evidenceDir, 'task-61-official-collector-matrix-http.json'),
  }
}

export function buildOfficialCollectorMatrixSummary(rows, meta = {}) {
  const lines = []

  if (normalizeOptionalValue(meta.generatedAt)) {
    lines.push(`generated_at=${normalizeOptionalValue(meta.generatedAt)}`)
  }
  if (normalizeOptionalValue(meta.source)) {
    lines.push(`source=${normalizeOptionalValue(meta.source)}`)
  }
  if (normalizeOptionalValue(meta.backendBaseUrl)) {
    lines.push(`backend_base_url=${normalizeOptionalValue(meta.backendBaseUrl)}`)
  }
  lines.push('')

  for (const row of rows) {
    lines.push(`collector=${row.collectorType}`)
    lines.push(`label=${row.label || ''}`)
    lines.push(`support_tier=${row.supportTier || ''}`)
    lines.push(`status=${row.status}`)
    lines.push(`processed_count=${Number.isFinite(row.processedCount) ? row.processedCount : 0}`)
    lines.push(`detail=${row.detail || ''}`)
    lines.push('')
  }

  lines.push(`passed_count=${rows.filter((row) => row.status === 'passed').length}`)
  lines.push(`failed_count=${rows.filter((row) => row.status === 'failed').length}`)

  return `${lines.join('\n')}\n`
}
