import { assertFocusedRealSmokeSchemaCase } from './focused-real-smoke-contract-helpers.mjs'

export const COLLECTORS_FOCUSED_SCHEMA_CASES_BY_TASK_ID = Object.freeze({
  'task-61': {
    summaryKeys: ['backend_base_url', 'settings_path', 'tasks', 'counts', 'http_evidence', 'backend_log'],
    httpKeys: ['health', 'start', 'stop', 'tasks'],
  },
})

export function assertFocusedRealSmokeCollectorsSchemaContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeSchemaCase(taskId, qaScriptFile, source, COLLECTORS_FOCUSED_SCHEMA_CASES_BY_TASK_ID, 'collectors-focused schema contract case')
}
