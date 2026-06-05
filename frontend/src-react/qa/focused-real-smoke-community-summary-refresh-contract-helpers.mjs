export function buildSuccessfulCommunitySummaryRefreshSchemaCase({
  summaryKeys = [],
  httpKeys = ['health', 'before_summary', 'regenerate', 'after_summary'],
} = {}) {
  return {
    summaryKeys: [
      'community_id',
      'initial_summary',
      'refreshed_summary',
      'fake_ollama_generate_requests',
      ...summaryKeys,
    ],
    httpKeys,
  }
}

export function buildSuccessfulCommunitySummaryRefreshValueCase({
  patterns = [],
  tailPatterns = [
    /community_id:\s*seedPayload\.community_id/,
    /initial_summary:\s*httpEvidence\.beforeSummary\.json\?\.summary/,
    /refreshed_summary:\s*httpEvidence\.afterSummary\.json\?\.summary/,
    /before_summary:\s*httpEvidence\.beforeSummary\.json/,
    /regenerate:\s*httpEvidence\.regenerate\.json/,
    /after_summary:\s*httpEvidence\.afterSummary\.json/,
  ],
} = {}) {
  return {
    patterns: [
      ...patterns,
      ...tailPatterns,
    ],
  }
}
