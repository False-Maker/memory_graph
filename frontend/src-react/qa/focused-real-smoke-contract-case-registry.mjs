import { RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS } from './focused-real-smoke-task-registry.mjs'

const HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID = Object.freeze({
  'task-24': { qaScriptFile: 't24-search-navigation-real-smoke.mjs' },
  'task-25': { qaScriptFile: 't25-memory-community-detail-real-smoke.mjs' },
  'task-27': { qaScriptFile: 't27-community-summary-real-smoke.mjs' },
  'task-28': { qaScriptFile: 't28-dashboard-real-smoke.mjs' },
  'task-39': { qaScriptFile: 't39-search-community-stale-link-real-smoke.mjs' },
  'task-42': { qaScriptFile: 't42-search-community-data-failure-real-smoke.mjs' },
  'task-44': { qaScriptFile: 't44-search-community-summary-facet-failure-real-smoke.mjs' },
  'task-58': { qaScriptFile: 't58-search-source-community-summary-facet-failure-real-smoke.mjs' },
  'task-59': { qaScriptFile: 't59-search-result-community-stale-link-real-smoke.mjs' },
  'task-60': { qaScriptFile: 't60-search-source-community-data-failure-real-smoke.mjs' },
})

const DASHBOARD_ADJACENT_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID = Object.freeze({
  'task-45': { qaScriptFile: 't45-dashboard-recent-memory-failure-real-smoke.mjs' },
  'task-46': { qaScriptFile: 't46-dashboard-recent-memory-write-real-smoke.mjs' },
  'task-47': { qaScriptFile: 't47-dashboard-recent-memory-community-real-smoke.mjs' },
  'task-48': { qaScriptFile: 't48-dashboard-view-all-memories-real-smoke.mjs' },
  'task-49': { qaScriptFile: 't49-dashboard-stat-navigation-real-smoke.mjs' },
  'task-50': { qaScriptFile: 't50-dashboard-stat-graph-empty-real-smoke.mjs' },
  'task-51': { qaScriptFile: 't51-dashboard-stat-communities-empty-real-smoke.mjs' },
  'task-52': { qaScriptFile: 't52-dashboard-stat-memories-empty-real-smoke.mjs' },
  'task-53': { qaScriptFile: 't53-dashboard-stat-memories-failure-real-smoke.mjs' },
  'task-54': { qaScriptFile: 't54-dashboard-stat-communities-failure-real-smoke.mjs' },
  'task-55': { qaScriptFile: 't55-dashboard-stat-graph-failure-real-smoke.mjs' },
})

const REMAINING_WEB_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID = Object.freeze({
  'task-26': { qaScriptFile: 't26-graph-real-smoke.mjs' },
  'task-29': { qaScriptFile: 't29-community-summary-llm-real-smoke.mjs' },
  'task-30': { qaScriptFile: 't30-dashboard-search-aggregate-real-smoke.mjs' },
  'task-31': { qaScriptFile: 't31-memories-list-real-smoke.mjs' },
  'task-32': { qaScriptFile: 't32-communities-navigation-real-smoke.mjs' },
  'task-33': { qaScriptFile: 't33-search-source-detail-failure-real-smoke.mjs' },
  'task-34': { qaScriptFile: 't34-memories-write-real-smoke.mjs' },
  'task-35': { qaScriptFile: 't35-memories-detail-write-real-smoke.mjs' },
  'task-36': { qaScriptFile: 't36-search-source-detail-missing-memory-id-real-smoke.mjs' },
  'task-37': { qaScriptFile: 't37-memories-detail-failure-real-smoke.mjs' },
  'task-38': { qaScriptFile: 't38-communities-detail-failure-real-smoke.mjs' },
  'task-40': { qaScriptFile: 't40-communities-lineage-failure-real-smoke.mjs' },
  'task-41': { qaScriptFile: 't41-communities-data-failure-real-smoke.mjs' },
  'task-43': { qaScriptFile: 't43-community-summary-facet-failure-real-smoke.mjs' },
  'task-56': { qaScriptFile: 't56-search-memory-detail-write-real-smoke.mjs' },
  'task-57': { qaScriptFile: 't57-search-memory-detail-failure-real-smoke.mjs' },
})

const SETTINGS_IMPORT_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID = Object.freeze({
  'task-22': { qaScriptFile: 't22-settings-secret-store-real-smoke.mjs' },
  'task-23': { qaScriptFile: 't23-import-diagnostics-real-smoke.mjs' },
})

const COLLECTORS_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID = Object.freeze({
  'task-61': { qaScriptFile: 't61-official-collector-smoke.mjs' },
})

const RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID = Object.freeze({
  ...HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID,
  ...DASHBOARD_ADJACENT_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID,
  ...REMAINING_WEB_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID,
  ...SETTINGS_IMPORT_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID,
  ...COLLECTORS_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID,
})

export const HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS = Object.freeze(
  Object.keys(HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID).sort()
)

const HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_ID_SET = new Set(HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS)

export const RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES = Object.freeze(
  RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS.map((taskId) => Object.freeze({
    taskId,
    signalTier: HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_ID_SET.has(taskId) ? 'high_signal' : 'baseline',
    qaScriptFile: RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASE_METADATA_BY_TASK_ID[taskId]?.qaScriptFile ?? null,
  }))
)

export const RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES_BY_TASK_ID = Object.freeze(
  Object.fromEntries(RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES.map((item) => [item.taskId, item]))
)

export const HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES = Object.freeze(
  RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES.filter((item) => item.signalTier === 'high_signal')
)

export const HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES_BY_TASK_ID = Object.freeze(
  Object.fromEntries(HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES.map((item) => [item.taskId, item]))
)

export function getReleaseCriticalFocusedRealSmokeContractCase(taskId) {
  return RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES_BY_TASK_ID[taskId] ?? null
}

export function getHighSignalFocusedRealSmokeContractCase(taskId) {
  return HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES_BY_TASK_ID[taskId] ?? null
}
