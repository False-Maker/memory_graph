import { assertFocusedRealSmokeValueCase } from './focused-real-smoke-contract-helpers.mjs'

export const COLLECTORS_FOCUSED_VALUE_CASES_BY_TASK_ID = Object.freeze({
  'task-61': {
    patterns: [
      /command:\s*'npm --prefix frontend run qa:real-stack-smoke:collectors:official'/,
      /status:\s*'passed'/,
      /http_evidence:\s*'\.sisyphus\/evidence\/task-61-official-collector-matrix-http\.json'/,
      /backend_log:\s*'\.sisyphus\/evidence\/task-61-official-collector-matrix-backend\.log'/,
      /health:\s*healthResponse\.json/,
      /start:\s*startResponse\.json/,
      /stop:\s*stopResponse\.json/,
      /tasks,/,
    ],
  },
})

export function assertFocusedRealSmokeCollectorsValueContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeValueCase(taskId, qaScriptFile, source, COLLECTORS_FOCUSED_VALUE_CASES_BY_TASK_ID, {
    missingCaseLabel: 'collectors-focused value contract case',
    missingBindingLabel: 'expected collectors-focused evidence binding',
  })
}
