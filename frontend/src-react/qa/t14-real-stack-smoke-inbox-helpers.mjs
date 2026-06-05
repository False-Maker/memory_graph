function normalizeChecks(checks) {
  if (!Array.isArray(checks)) return []
  const normalized = checks
    .map((item) => String(item || '').trim())
    .filter(Boolean)
  return Array.from(new Set(normalized))
}

export function normalizeInboxSmokeResult(result) {
  const status = String(result?.status || '').trim().toLowerCase() === 'passed'
    ? 'passed'
    : 'failed'
  const checks = normalizeChecks(result?.checks)
  const note = typeof result?.note === 'string' && result.note.trim()
    ? result.note.trim()
    : ''
  return { status, checks, note }
}

export function buildInboxSmokeSummaryLines(result) {
  const normalized = normalizeInboxSmokeResult(result)
  return [
    `inbox_smoke=${normalized.status}`,
    `inbox_smoke_checks=${normalized.checks.join(',') || 'none'}`,
    `inbox_smoke_note=${normalized.note || 'none'}`
  ]
}

