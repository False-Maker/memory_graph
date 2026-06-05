export function extractSummaryField(raw, field) {
  if (typeof raw !== 'string') {
    return ''
  }

  const match = raw.match(new RegExp(`^${field}=(.*)$`, 'm'))
  return match ? match[1] : ''
}

function normalizeOptionalValue(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

export function buildProviderMatrixSummary(rows, meta = {}) {
  const lines = []

  if (normalizeOptionalValue(meta.generatedAt)) {
    lines.push(`generated_at=${normalizeOptionalValue(meta.generatedAt)}`)
  }
  if (normalizeOptionalValue(meta.source)) {
    lines.push(`source=${normalizeOptionalValue(meta.source)}`)
  }
  if (normalizeOptionalValue(meta.readinessEvidence)) {
    lines.push(`readiness_evidence=${normalizeOptionalValue(meta.readinessEvidence)}`)
  }
  if (normalizeOptionalValue(meta.providerScope)) {
    lines.push(`provider_scope=${normalizeOptionalValue(meta.providerScope)}`)
  }
  if (lines.length > 0) {
    lines.push('')
  }

  for (const row of rows) {
    lines.push(`provider=${row.provider}`)
    lines.push(`status=${row.status}`)
    lines.push(`readiness=${row.readiness || ''}`)
    lines.push(`reason=${row.reason || ''}`)
    lines.push(`exit_code=${row.exitCode}`)
    lines.push(`command=${row.command}`)
    lines.push(`hint=${row.hint || ''}`)
    lines.push(`evidence=${row.evidence || ''}`)
    lines.push(`log=${row.log || ''}`)
    lines.push(`summary_excerpt=${row.summaryExcerpt || ''}`)
    lines.push('')
  }

  lines.push(`passed_count=${rows.filter((row) => row.status === 'passed').length}`)
  lines.push(`blocked_count=${rows.filter((row) => row.status === 'blocked').length}`)
  lines.push(`failed_count=${rows.filter((row) => row.status === 'failed').length}`)

  return `${lines.join('\n')}\n`
}
