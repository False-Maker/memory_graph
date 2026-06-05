const BASE_TASK_GROUPS = {
  'settings-import-focused': ['task-22', 'task-23'],
  'collectors-focused': ['task-61'],
  'mainline-core': ['task-24', 'task-25', 'task-27', 'task-28'],
  'search-community-adjacent': ['task-39', 'task-42', 'task-44', 'task-58', 'task-59', 'task-60'],
  'remaining-web-focused': [
    'task-26',
    'task-29',
    'task-30',
    'task-31',
    'task-32',
    'task-33',
    'task-34',
    'task-35',
    'task-36',
    'task-37',
    'task-38',
    'task-40',
    'task-41',
    'task-43',
    'task-56',
    'task-57',
  ],
  'dashboard-adjacent': [
    'task-45',
    'task-46',
    'task-47',
    'task-48',
    'task-49',
    'task-50',
    'task-51',
    'task-52',
    'task-53',
    'task-54',
    'task-55',
  ],
}

const releaseCriticalTaskIds = [
  ...BASE_TASK_GROUPS['settings-import-focused'],
  ...BASE_TASK_GROUPS['collectors-focused'],
  ...BASE_TASK_GROUPS['mainline-core'],
  ...BASE_TASK_GROUPS['search-community-adjacent'],
  ...BASE_TASK_GROUPS['remaining-web-focused'],
  ...BASE_TASK_GROUPS['dashboard-adjacent'],
]

export const FOCUSED_REAL_SMOKE_TASK_GROUPS = Object.freeze({
  ...Object.fromEntries(
    Object.entries(BASE_TASK_GROUPS).map(([groupName, taskIds]) => [groupName, Object.freeze([...taskIds])])
  ),
  'release-critical': Object.freeze([...releaseCriticalTaskIds]),
})

export const RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS = FOCUSED_REAL_SMOKE_TASK_GROUPS['release-critical']

export const FOCUSED_REAL_SMOKE_WORKFLOW_JOBS = Object.freeze([
  {
    jobId: 'settings-secret-store-real-smoke',
    artifactName: 'settings-secret-store-real-smoke-evidence',
    evidencePrefix: 'task-22-settings-secret-store-real',
    runScript: 'qa:real-stack-smoke:settings:secret-store',
    taskId: 'task-22',
    includeSeed: false,
  },
  {
    jobId: 'import-diagnostics-real-smoke',
    artifactName: 'import-diagnostics-real-smoke-evidence',
    evidencePrefix: 'task-23-import-diagnostics-real',
    runScript: 'qa:real-stack-smoke:import:diagnostics',
    taskId: 'task-23',
    includeSeed: false,
  },
  {
    jobId: 'official-collector-real-smoke',
    artifactName: 'official-collector-real-smoke-evidence',
    evidencePrefix: 'task-61-official-collector-matrix',
    runScript: 'qa:real-stack-smoke:collectors:official',
    taskId: 'task-61',
    includeSeed: false,
    includeDefaultPng: false,
    extraPaths: Object.freeze([
      '.sisyphus/evidence/task-61-official-collector-matrix-http.json',
      '.sisyphus/evidence/task-61-official-collector-matrix-backend.log',
    ]),
  },
  {
    jobId: 'search-navigation-real-smoke',
    artifactName: 'search-navigation-real-smoke-evidence',
    evidencePrefix: 'task-24-search-navigation-real',
    runScript: 'qa:real-stack-smoke:search:navigation',
    taskId: 'task-24',
  },
  {
    jobId: 'memory-community-detail-real-smoke',
    artifactName: 'memory-community-detail-real-smoke-evidence',
    evidencePrefix: 'task-25-memory-community-detail-real',
    runScript: 'qa:real-stack-smoke:memories:communities',
    taskId: 'task-25',
  },
  {
    jobId: 'graph-real-smoke',
    artifactName: 'graph-real-smoke-evidence',
    evidencePrefix: 'task-26-graph-real',
    runScript: 'qa:real-stack-smoke:graph',
    taskId: 'task-26',
  },
  {
    jobId: 'community-summary-real-smoke',
    artifactName: 'community-summary-real-smoke-evidence',
    evidencePrefix: 'task-27-community-summary-real',
    runScript: 'qa:real-stack-smoke:communities:summary',
    taskId: 'task-27',
  },
  {
    jobId: 'dashboard-real-smoke',
    artifactName: 'dashboard-real-smoke-evidence',
    evidencePrefix: 'task-28-dashboard-real',
    runScript: 'qa:real-stack-smoke:dashboard',
    taskId: 'task-28',
  },
  {
    jobId: 'dashboard-recent-memory-failure-real-smoke',
    artifactName: 'dashboard-recent-memory-failure-real-smoke-evidence',
    evidencePrefix: 'task-45-dashboard-recent-memory-failure-real',
    runScript: 'qa:real-stack-smoke:dashboard:recent-memory:failure',
    taskId: 'task-45',
    includeDefaultPng: false,
    extraPaths: Object.freeze([
      '.sisyphus/evidence/task-45-dashboard-recent-memory-failure-real-stale-detail.png',
      '.sisyphus/evidence/task-45-dashboard-recent-memory-failure-real-empty-dashboard.png',
    ]),
  },
  {
    jobId: 'dashboard-recent-memory-write-real-smoke',
    artifactName: 'dashboard-recent-memory-write-real-smoke-evidence',
    evidencePrefix: 'task-46-dashboard-recent-memory-write-real',
    runScript: 'qa:real-stack-smoke:dashboard:recent-memory:write-path',
    taskId: 'task-46',
  },
  {
    jobId: 'dashboard-recent-memory-community-real-smoke',
    artifactName: 'dashboard-recent-memory-community-real-smoke-evidence',
    evidencePrefix: 'task-47-dashboard-recent-memory-community-real',
    runScript: 'qa:real-stack-smoke:dashboard:recent-memory:community-navigation',
    taskId: 'task-47',
  },
  {
    jobId: 'dashboard-view-all-memories-real-smoke',
    artifactName: 'dashboard-view-all-memories-real-smoke-evidence',
    evidencePrefix: 'task-48-dashboard-view-all-memories-real',
    runScript: 'qa:real-stack-smoke:dashboard:view-all:memories',
    taskId: 'task-48',
  },
  {
    jobId: 'dashboard-stat-navigation-real-smoke',
    artifactName: 'dashboard-stat-navigation-real-smoke-evidence',
    evidencePrefix: 'task-49-dashboard-stat-navigation-real',
    runScript: 'qa:real-stack-smoke:dashboard:stats-navigation',
    taskId: 'task-49',
  },
  {
    jobId: 'dashboard-stat-graph-empty-real-smoke',
    artifactName: 'dashboard-stat-graph-empty-real-smoke-evidence',
    evidencePrefix: 'task-50-dashboard-stat-graph-empty-real',
    runScript: 'qa:real-stack-smoke:dashboard:stats:graph:empty',
    taskId: 'task-50',
    includeSeed: false,
  },
  {
    jobId: 'dashboard-stat-communities-empty-real-smoke',
    artifactName: 'dashboard-stat-communities-empty-real-smoke-evidence',
    evidencePrefix: 'task-51-dashboard-stat-communities-empty-real',
    runScript: 'qa:real-stack-smoke:dashboard:stats:communities:empty',
    taskId: 'task-51',
    includeSeed: false,
  },
  {
    jobId: 'dashboard-stat-memories-empty-real-smoke',
    artifactName: 'dashboard-stat-memories-empty-real-smoke-evidence',
    evidencePrefix: 'task-52-dashboard-stat-memories-empty-real',
    runScript: 'qa:real-stack-smoke:dashboard:stats:memories:empty',
    taskId: 'task-52',
    includeSeed: false,
  },
  {
    jobId: 'dashboard-stat-memories-failure-real-smoke',
    artifactName: 'dashboard-stat-memories-failure-real-smoke-evidence',
    evidencePrefix: 'task-53-dashboard-stat-memories-failure-real',
    runScript: 'qa:real-stack-smoke:dashboard:stats:memories:failure',
    taskId: 'task-53',
    includeSeed: false,
  },
  {
    jobId: 'dashboard-stat-communities-failure-real-smoke',
    artifactName: 'dashboard-stat-communities-failure-real-smoke-evidence',
    evidencePrefix: 'task-54-dashboard-stat-communities-failure-real',
    runScript: 'qa:real-stack-smoke:dashboard:stats:communities:failure',
    taskId: 'task-54',
    includeSeed: false,
  },
  {
    jobId: 'dashboard-stat-graph-failure-real-smoke',
    artifactName: 'dashboard-stat-graph-failure-real-smoke-evidence',
    evidencePrefix: 'task-55-dashboard-stat-graph-failure-real',
    runScript: 'qa:real-stack-smoke:dashboard:stats:graph:failure',
    taskId: 'task-55',
    includeSeed: false,
  },
  {
    jobId: 'community-summary-llm-real-smoke',
    artifactName: 'community-summary-llm-real-smoke-evidence',
    evidencePrefix: 'task-29-community-summary-llm-real',
    runScript: 'qa:real-stack-smoke:communities:summary:llm',
    taskId: 'task-29',
  },
  {
    jobId: 'dashboard-search-aggregate-real-smoke',
    artifactName: 'dashboard-search-aggregate-real-smoke-evidence',
    evidencePrefix: 'task-30-dashboard-search-aggregate-real',
    runScript: 'qa:real-stack-smoke:dashboard:search:aggregate',
    taskId: 'task-30',
  },
  {
    jobId: 'memories-list-real-smoke',
    artifactName: 'memories-list-real-smoke-evidence',
    evidencePrefix: 'task-31-memories-list-real',
    runScript: 'qa:real-stack-smoke:memories:list',
    taskId: 'task-31',
  },
  {
    jobId: 'memories-write-real-smoke',
    artifactName: 'memories-write-real-smoke-evidence',
    evidencePrefix: 'task-34-memories-write-real',
    runScript: 'qa:real-stack-smoke:memories:write-path',
    taskId: 'task-34',
  },
  {
    jobId: 'memories-detail-write-real-smoke',
    artifactName: 'memories-detail-write-real-smoke-evidence',
    evidencePrefix: 'task-35-memories-detail-write-real',
    runScript: 'qa:real-stack-smoke:memories:detail:write-path',
    taskId: 'task-35',
  },
  {
    jobId: 'memories-detail-failure-real-smoke',
    artifactName: 'memories-detail-failure-real-smoke-evidence',
    evidencePrefix: 'task-37-memories-detail-failure-real',
    runScript: 'qa:real-stack-smoke:memories:detail:failure',
    taskId: 'task-37',
    includeDefaultPng: false,
    extraPaths: Object.freeze([
      '.sisyphus/evidence/task-37-memories-detail-failure-real-missing.png',
      '.sisyphus/evidence/task-37-memories-detail-failure-real-deleted.png',
    ]),
  },
  {
    jobId: 'communities-navigation-real-smoke',
    artifactName: 'communities-navigation-real-smoke-evidence',
    evidencePrefix: 'task-32-communities-navigation-real',
    runScript: 'qa:real-stack-smoke:communities:navigation',
    taskId: 'task-32',
  },
  {
    jobId: 'communities-detail-failure-real-smoke',
    artifactName: 'communities-detail-failure-real-smoke-evidence',
    evidencePrefix: 'task-38-communities-detail-failure-real',
    runScript: 'qa:real-stack-smoke:communities:detail:failure',
    taskId: 'task-38',
    includeDefaultPng: false,
    extraPaths: Object.freeze([
      '.sisyphus/evidence/task-38-communities-detail-failure-real-missing.png',
      '.sisyphus/evidence/task-38-communities-detail-failure-real-stale.png',
    ]),
  },
  {
    jobId: 'communities-lineage-failure-real-smoke',
    artifactName: 'communities-lineage-failure-real-smoke-evidence',
    evidencePrefix: 'task-40-communities-lineage-failure-real',
    runScript: 'qa:real-stack-smoke:communities:lineage:failure',
    taskId: 'task-40',
  },
  {
    jobId: 'communities-data-failure-real-smoke',
    artifactName: 'communities-data-failure-real-smoke-evidence',
    evidencePrefix: 'task-41-communities-data-failure-real',
    runScript: 'qa:real-stack-smoke:communities:data:failure',
    taskId: 'task-41',
  },
  {
    jobId: 'communities-summary-facet-failure-real-smoke',
    artifactName: 'communities-summary-facet-failure-real-smoke-evidence',
    evidencePrefix: 'task-43-community-summary-facet-failure-real',
    runScript: 'qa:real-stack-smoke:communities:summary:facet-failure',
    taskId: 'task-43',
  },
  {
    jobId: 'search-source-community-stale-link-real-smoke',
    artifactName: 'search-source-community-stale-link-real-smoke-evidence',
    evidencePrefix: 'task-39-search-community-stale-link-real',
    runScript: 'qa:real-stack-smoke:search:source-community:stale-link',
    taskId: 'task-39',
  },
  {
    jobId: 'search-result-community-data-failure-real-smoke',
    artifactName: 'search-result-community-data-failure-real-smoke-evidence',
    evidencePrefix: 'task-42-search-community-data-failure-real',
    runScript: 'qa:real-stack-smoke:search:result-community:data-failure',
    taskId: 'task-42',
  },
  {
    jobId: 'search-result-community-summary-facet-failure-real-smoke',
    artifactName: 'search-result-community-summary-facet-failure-real-smoke-evidence',
    evidencePrefix: 'task-44-search-community-summary-facet-failure-real',
    runScript: 'qa:real-stack-smoke:search:result-community:summary:facet-failure',
    taskId: 'task-44',
  },
  {
    jobId: 'search-source-detail-failure-real-smoke',
    artifactName: 'search-source-detail-failure-real-smoke-evidence',
    evidencePrefix: 'task-33-search-source-detail-failure-real',
    runScript: 'qa:real-stack-smoke:search:source-detail:failure',
    taskId: 'task-33',
  },
  {
    jobId: 'search-source-detail-missing-memory-id-real-smoke',
    artifactName: 'search-source-detail-missing-memory-id-real-smoke-evidence',
    evidencePrefix: 'task-36-search-source-detail-missing-memory-id-real',
    runScript: 'qa:real-stack-smoke:search:source-detail:missing-memory-id',
    taskId: 'task-36',
  },
  {
    jobId: 'search-memory-detail-write-real-smoke',
    artifactName: 'search-memory-detail-write-real-smoke-evidence',
    evidencePrefix: 'task-56-search-memory-detail-write-real',
    runScript: 'qa:real-stack-smoke:search:memory:detail:write-path',
    taskId: 'task-56',
  },
  {
    jobId: 'search-memory-detail-failure-real-smoke',
    artifactName: 'search-memory-detail-failure-real-smoke-evidence',
    evidencePrefix: 'task-57-search-memory-detail-failure-real',
    runScript: 'qa:real-stack-smoke:search:memory:detail:failure',
    taskId: 'task-57',
  },
  {
    jobId: 'search-source-community-summary-facet-failure-real-smoke',
    artifactName: 'search-source-community-summary-facet-failure-real-smoke-evidence',
    evidencePrefix: 'task-58-search-source-community-summary-facet-failure-real',
    runScript: 'qa:real-stack-smoke:search:source-community:summary:facet-failure',
    taskId: 'task-58',
  },
  {
    jobId: 'search-result-community-stale-link-real-smoke',
    artifactName: 'search-result-community-stale-link-real-smoke-evidence',
    evidencePrefix: 'task-59-search-result-community-stale-link-real',
    runScript: 'qa:real-stack-smoke:search:result-community:stale-link',
    taskId: 'task-59',
  },
  {
    jobId: 'search-source-community-data-failure-real-smoke',
    artifactName: 'search-source-community-data-failure-real-smoke-evidence',
    evidencePrefix: 'task-60-search-source-community-data-failure-real',
    runScript: 'qa:real-stack-smoke:search:source-community:data-failure',
    taskId: 'task-60',
  },
])

export const FOCUSED_REAL_SMOKE_WORKFLOW_JOBS_BY_TASK_ID = Object.freeze(
  Object.fromEntries(FOCUSED_REAL_SMOKE_WORKFLOW_JOBS.map((job) => [job.taskId, job]))
)

export function getFocusedRealSmokeWorkflowJob(taskId) {
  return FOCUSED_REAL_SMOKE_WORKFLOW_JOBS_BY_TASK_ID[taskId] ?? null
}

export function getFocusedRealSmokeEvidenceFiles(taskId) {
  const workflowJob = getFocusedRealSmokeWorkflowJob(taskId)
  if (!workflowJob?.evidencePrefix) return null

  return {
    summaryFile: `${workflowJob.evidencePrefix}-summary.json`,
    httpFile: `${workflowJob.evidencePrefix}-http.json`,
  }
}
