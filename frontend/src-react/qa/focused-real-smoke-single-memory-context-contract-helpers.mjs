export function buildSingleMemoryContextSchemaCase({
  summaryMemoryIdKey,
  summaryContextCountKey,
  includeCommunityId = false,
  extraSummaryKeys = [],
  httpKeys = [],
} = {}) {
  return {
    summaryKeys: [
      ...(summaryMemoryIdKey ? [summaryMemoryIdKey] : []),
      ...(includeCommunityId ? ['community_id'] : []),
      ...(summaryContextCountKey ? [summaryContextCountKey] : []),
      ...extraSummaryKeys,
    ],
    httpKeys: ['health', 'communities', 'memory_context', ...httpKeys],
  }
}

export function buildSingleMemoryContextValueCase({
  memoryIdPattern,
  contextCountPattern,
  patterns = [],
  tailPatterns = [/memory_context:\s*httpEvidence\.memoryContext\.json/],
} = {}) {
  return {
    patterns: [
      ...(memoryIdPattern ? [memoryIdPattern] : []),
      ...(contextCountPattern ? [contextCountPattern] : []),
      ...patterns,
      ...tailPatterns,
    ],
  }
}
