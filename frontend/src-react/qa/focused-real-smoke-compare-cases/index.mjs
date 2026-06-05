import { COLLECTORS_FOCUSED_TASK_CASES } from './collectors-focused.mjs'
import { DASHBOARD_ADJACENT_TASK_CASES } from './dashboard-adjacent.mjs'
import { MAINLINE_CORE_TASK_CASES } from './mainline-core.mjs'
import { REMAINING_WEB_FOCUSED_TASK_CASES } from './remaining-web-focused.mjs'
import { SEARCH_COMMUNITY_ADJACENT_TASK_CASES } from './search-community-adjacent.mjs'
import { SETTINGS_IMPORT_TASK_CASES } from './settings-import.mjs'

function mergeTaskCaseGroups(...groups) {
  const merged = {}

  for (const group of groups) {
    for (const [taskId, taskCase] of Object.entries(group)) {
      if (taskId in merged) {
        throw new Error(`Duplicate focused smoke task case: ${taskId}`)
      }
      merged[taskId] = taskCase
    }
  }

  return Object.freeze(merged)
}

export const TASK_CASES = mergeTaskCaseGroups(
  SETTINGS_IMPORT_TASK_CASES,
  COLLECTORS_FOCUSED_TASK_CASES,
  MAINLINE_CORE_TASK_CASES,
  SEARCH_COMMUNITY_ADJACENT_TASK_CASES,
  DASHBOARD_ADJACENT_TASK_CASES,
  REMAINING_WEB_FOCUSED_TASK_CASES
)
