import {
  buildRuntimeDiagnosticsSummary,
  getFailedRuntimeDiagnosticsChecks,
  normalizeRuntimeDiagnostics,
} from './settings-runtime-diagnostics.js'

export function buildImportRuntimeDiagnosticsSummary(runtimeDiagnostics) {
  const normalized = normalizeRuntimeDiagnostics(runtimeDiagnostics)
  const failedChecks = getFailedRuntimeDiagnosticsChecks(normalized)
  const sharedSummary = buildRuntimeDiagnosticsSummary(normalized)

  if (normalized.status === 'unknown') {
    return {
      tone: 'neutral',
      message: '尚未获取导入/同步运行诊断。',
      detail: ''
    }
  }

  if (failedChecks.length > 0) {
    return {
      tone: 'error',
      message: '核心运行依赖未通过诊断，导入/同步结果当前不可完全信任。',
      detail: [sharedSummary.message, sharedSummary.detail].filter(Boolean).join('；')
    }
  }

  if (sharedSummary.tone === 'warning') {
    return {
      tone: 'warning',
      message: '核心运行依赖健康，但同步链路仍有待处理项。',
      detail: [
        sharedSummary.detail,
        '建议：先处理 source 冲突/路径问题，再执行 push、pull 或双向同步。',
      ].filter(Boolean).join('；')
    }
  }

  if (normalized.task_chain.status === 'not_configured') {
    return {
      tone: 'success',
      message: '当前没有配置外部记忆源；不影响文件、目录和会话导入。',
      detail: '如需任务链同步，再到“外部记忆源”页签保存 source。'
    }
  }

  return {
    tone: 'success',
    message: '核心运行依赖健康，导入/同步链路当前可信。',
    detail: `已配置 source：${normalized.task_chain.configured_sources ?? 0}`
  }
}
