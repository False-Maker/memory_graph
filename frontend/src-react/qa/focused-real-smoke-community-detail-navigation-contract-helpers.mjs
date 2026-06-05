export function buildCommunityDetailNavigationSchemaCase({
  summaryKeys = [],
  includeRecentMemoriesHttp = false,
} = {}) {
  return {
    summaryKeys: [
      'community_id',
      'memory_context_communities',
      'community_entities_total',
      'community_relationships_total',
      'ancestors_total',
      'descendants_total',
      ...summaryKeys,
    ],
    httpKeys: [
      'health',
      ...(includeRecentMemoriesHttp ? ['recent_memories'] : []),
      'memory_detail',
      'memory_context',
      'community_detail',
      'community_entities',
      'community_relationships',
      'community_ancestors',
      'community_descendants',
    ],
  }
}

export function buildCommunityDetailNavigationValueCase({
  patterns = [],
  tailPatterns = [
    /community_id:\s*seedPayload\.community_id/,
    /memory_context_communities:\s*httpEvidence\.memoryContext\.json\?\.total_communities/,
    /community_entities_total:\s*httpEvidence\.communityEntities\.json\?\.total/,
    /community_relationships_total:\s*httpEvidence\.communityRelationships\.json\?\.total/,
    /community_relationships:\s*httpEvidence\.communityRelationships\.json/,
    /community_ancestors:\s*httpEvidence\.ancestors\.json/,
    /community_descendants:\s*httpEvidence\.descendants\.json/,
  ],
} = {}) {
  return {
    patterns: [
      ...patterns,
      ...tailPatterns,
    ],
  }
}
