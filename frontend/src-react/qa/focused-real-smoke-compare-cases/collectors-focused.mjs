import { createTaskCase } from './helpers.mjs'

export const COLLECTORS_FOCUSED_TASK_CASES = {
  'task-61': createTaskCase('task-61', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        backend_base_url: summary.backend_base_url ?? null,
        task_statuses: Array.isArray(summary.tasks)
          ? summary.tasks.map((task) => ({
              collector: task.collectorType ?? null,
              support_tier: task.supportTier ?? null,
              status: task.status ?? null,
            }))
          : [],
        passed_count: summary.counts?.passed ?? null,
        failed_count: summary.counts?.failed ?? null,
        health_status: http.health?.status ?? null,
        start_status: http.start?.status ?? null,
        stop_status: http.stop?.status ?? null,
        processed_counts: Array.isArray(http.tasks)
          ? http.tasks.map((task) => ({
              collector: task.collectorType ?? null,
              processed_count: task.processedCount ?? null,
            }))
          : [],
      }
    },
  }),
}
