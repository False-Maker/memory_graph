import { normalizeList } from './focused-real-smoke-compare-cases/helpers.mjs'

function getDiagnosticsProvider(diagnostics) {
  return diagnostics?.checks?.config?.provider
    ?? diagnostics?.checks?.provider?.current_provider
    ?? null
}

export function buildSettingsImportDiagnosticsNormalizeFragment({
  summary,
  diagnostics,
  summaryStatusKey,
  summaryProviderOkKey,
  providerField,
  providerOkField,
  taskChainStatusField,
  configuredSourcesField,
  sourceLabelsField,
  sourceStatusesField,
  conflictsField,
  recentFailureComponentsField,
} = {}) {
  return {
    ...(summaryStatusKey ? { [summaryStatusKey]: summary?.[summaryStatusKey] ?? null } : {}),
    ...(summaryProviderOkKey ? { [summaryProviderOkKey]: summary?.[summaryProviderOkKey] ?? null } : {}),
    ...(providerField ? { [providerField]: getDiagnosticsProvider(diagnostics) } : {}),
    ...(providerOkField ? { [providerOkField]: diagnostics?.checks?.provider?.ok ?? null } : {}),
    ...(taskChainStatusField ? { [taskChainStatusField]: diagnostics?.task_chain?.status ?? null } : {}),
    ...(configuredSourcesField ? { [configuredSourcesField]: diagnostics?.task_chain?.configured_sources ?? null } : {}),
    ...(sourceLabelsField ? {
      [sourceLabelsField]: normalizeList(diagnostics?.task_chain?.sources, (item) => item?.label).filter(Boolean),
    } : {}),
    ...(sourceStatusesField ? {
      [sourceStatusesField]: normalizeList(diagnostics?.task_chain?.sources, (item) => item?.state_status).filter(Boolean),
    } : {}),
    ...(conflictsField ? { [conflictsField]: diagnostics?.task_chain?.sources?.[0]?.conflicts ?? null } : {}),
    ...(recentFailureComponentsField ? {
      [recentFailureComponentsField]: normalizeList(diagnostics?.recent_failures, (item) => item?.component).filter(Boolean),
    } : {}),
  }
}

export function buildSettingsImportDiagnosticsSummaryKeys({
  statusKey,
  providerOkKey,
  taskChainStatusKey,
  configuredSourcesKey,
  conflictsKey,
  recentFailuresCountKey,
  extraKeys = [],
} = {}) {
  return [
    ...(statusKey ? [statusKey] : []),
    ...(providerOkKey ? [providerOkKey] : []),
    ...(taskChainStatusKey ? [taskChainStatusKey] : []),
    ...(configuredSourcesKey ? [configuredSourcesKey] : []),
    ...(conflictsKey ? [conflictsKey] : []),
    ...(recentFailuresCountKey ? [recentFailuresCountKey] : []),
    ...extraKeys,
  ]
}

export function buildSettingsImportDiagnosticsValuePatterns({
  statusPattern,
  providerOkPattern,
  taskChainStatusPattern,
  configuredSourcesPattern,
  conflictsPattern,
  recentFailuresCountPattern,
  patterns = [],
  tailPatterns = [],
} = {}) {
  return [
    ...(statusPattern ? [statusPattern] : []),
    ...(providerOkPattern ? [providerOkPattern] : []),
    ...(taskChainStatusPattern ? [taskChainStatusPattern] : []),
    ...(configuredSourcesPattern ? [configuredSourcesPattern] : []),
    ...(conflictsPattern ? [conflictsPattern] : []),
    ...(recentFailuresCountPattern ? [recentFailuresCountPattern] : []),
    ...patterns,
    ...tailPatterns,
  ]
}
