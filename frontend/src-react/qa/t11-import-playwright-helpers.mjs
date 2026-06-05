let runSequence = 0

function toSafeNumber(value, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function nextRunId() {
  runSequence += 1
  return `run-${runSequence}`
}

export function buildImportRun(overrides = {}) {
  return {
    id: overrides.id || nextRunId(),
    status: String(overrides.status || 'succeeded'),
    run_type: String(overrides.run_type || 'unknown'),
    source: overrides.source || null,
    source_id: overrides.source_id || null,
    workspace_id: overrides.workspace_id || null,
    label: overrides.label || null,
    filename: overrides.filename || null,
    detail: overrides.detail || null,
    error: overrides.error || null,
    message: overrides.message || null,
    summary: overrides.summary || null,
    imported: toSafeNumber(overrides.imported, 0),
    attempted: toSafeNumber(overrides.attempted, 0),
    failed: toSafeNumber(overrides.failed, 0),
    skipped: toSafeNumber(overrides.skipped, 0),
    started_at: overrides.started_at || null,
    finished_at: overrides.finished_at || null,
    created_at: overrides.created_at || new Date().toISOString()
  }
}

export function buildDirectoryScanResponse({
  matchedPaths = [],
  skippedFiles = [],
  errors = []
} = {}) {
  return {
    total_files: matchedPaths.length + skippedFiles.length,
    conversation_files: matchedPaths.map((filePath) => ({ path: filePath, format: 'chatgpt' })),
    skipped_files: skippedFiles.map((item) => ({
      path: item.path,
      reason: item.reason || 'unsupported extension'
    })),
    errors
  }
}

export function createImportRunsStore(initialRuns = []) {
  let runs = initialRuns.map((item) => buildImportRun(item))

  return {
    prepend(run) {
      runs = [buildImportRun(run), ...runs]
    },
    list(limit = 10) {
      const safeLimit = Math.max(0, toSafeNumber(limit, 10))
      return runs.slice(0, safeLimit)
    },
    size() {
      return runs.length
    }
  }
}

export function toImportRunsApiPayload(store, requestUrl) {
  const parsed = new URL(requestUrl)
  const limitParam = parsed.searchParams.get('limit')
  const limit = limitParam ? toSafeNumber(limitParam, 10) : 10
  return {
    success: true,
    runs: store.list(limit)
  }
}
