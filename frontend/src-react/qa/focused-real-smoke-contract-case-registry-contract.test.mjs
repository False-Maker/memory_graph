import test from 'node:test'
import assert from 'node:assert/strict'

import {
  HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES,
  HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS,
  RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES,
  RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES_BY_TASK_ID,
  getReleaseCriticalFocusedRealSmokeContractCase,
} from './focused-real-smoke-contract-case-registry.mjs'
import {
  DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
  DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
} from './focused-real-smoke-dashboard-evidence-sample-assertions.mjs'
import {
  REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
  REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
} from './focused-real-smoke-remaining-web-evidence-sample-assertions.mjs'
import { EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID } from './focused-real-smoke-evidence-sample-assertions.mjs'
import {
  COLLECTORS_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
  COLLECTORS_FOCUSED_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
} from './focused-real-smoke-collectors-evidence-sample-assertions.mjs'
import {
  SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
  SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
} from './focused-real-smoke-settings-import-evidence-sample-assertions.mjs'
import {
  assertFocusedRealSmokeTaskIdCoverage,
  expectedFocusedRealSmokeCommand,
  readHighSignalFocusedRealSmokeQaScriptSource,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertMappedUniqueValues,
  assertSortedUniqueValuesMatch,
  assertUniqueValues,
} from './focused-real-smoke-registry-test-helpers.mjs'
import { RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS } from './focused-real-smoke-task-registry.mjs'

test('high-signal focused smoke contract registry stays unique and resolves to qa scripts plus workflow commands', async () => {
  assertFocusedRealSmokeTaskIdCoverage(
    RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES_BY_TASK_ID,
    RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS,
    'release-critical focused smoke contract registry'
  )
  assertUniqueValues(
    HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS,
    'high-signal focused smoke contract registry task ids'
  )
  assertMappedUniqueValues(
    HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES,
    (item) => item.qaScriptFile,
    'high-signal focused smoke contract registry qa script files'
  )
  assertFocusedRealSmokeTaskIdCoverage(
    EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS,
    'high-signal evidence sample assertions'
  )
  assertFocusedRealSmokeTaskIdCoverage(
    REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
    'remaining-web-focused evidence sample assertions'
  )
  assertFocusedRealSmokeTaskIdCoverage(
    DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
    'dashboard-adjacent evidence sample assertions'
  )
  assertFocusedRealSmokeTaskIdCoverage(
    SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
    'settings-import-focused evidence sample assertions'
  )
  assertFocusedRealSmokeTaskIdCoverage(
    COLLECTORS_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    COLLECTORS_FOCUSED_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
    'collectors-focused evidence sample assertions'
  )
  assert.equal(
    RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES.filter((item) => item.signalTier === 'high_signal').length,
    HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES.length,
    'high-signal subset drifted from the release-critical contract registry'
  )
  const semanticAssertionCoverage = [
    ...Object.keys(EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID),
    ...Object.keys(DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID),
    ...Object.keys(REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID),
    ...Object.keys(SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID),
    ...Object.keys(COLLECTORS_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID),
  ].sort()
  assertSortedUniqueValuesMatch(
    semanticAssertionCoverage,
    RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS,
    'release-critical semantic evidence assertion coverage drifted from the task registry'
  )

  for (const { taskId } of HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES) {
    const source = await readHighSignalFocusedRealSmokeQaScriptSource(taskId)
    assert.match(source, /summaryPayload/, `${taskId} qa script should expose summaryPayload`)
    assert.match(source, /httpEvidence/, `${taskId} qa script should expose httpEvidence`)
    assert.match(
      expectedFocusedRealSmokeCommand(taskId),
      /^npm --prefix frontend run qa:real-stack-smoke:/,
      `${taskId} workflow command should resolve to a focused real smoke script`
    )
  }

  for (const taskId of RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS) {
    const contractCase = getReleaseCriticalFocusedRealSmokeContractCase(taskId)
    assert.deepEqual(
      contractCase,
      RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_CONTRACT_CASES_BY_TASK_ID[taskId],
      `${taskId} should resolve through the release-critical contract case lookup`
    )
    assert.ok(contractCase, `Missing release-critical focused smoke contract case for ${taskId}`)
    assert.match(contractCase.signalTier, /^(high_signal|baseline)$/)
  }
})
