export function buildHighSignalCommunityMissingDetailSchemaCase({
  includeQuerySourceCommunityId = false,
  includeQueryHitCommunityId = false,
} = {}) {
  return {
    summaryKeys: [
      'community_id',
      'missing_community_id',
      'link_surface',
      ...(includeQuerySourceCommunityId ? ['query_source_community_id'] : []),
      ...(includeQueryHitCommunityId ? ['query_hit_community_id'] : []),
      'missing_detail_status',
    ],
    httpKeys: ['health', 'query', 'community_detail', 'missing_detail'],
  }
}

export function buildHighSignalCommunityDataFailureSchemaCase({
  includeQueryCommunityIds = false,
  includeQuerySourceCommunityId = false,
  includeCommunityTitle = false,
} = {}) {
  return {
    summaryKeys: [
      'target_community_id',
      ...(includeQueryCommunityIds ? ['query_community_ids'] : []),
      ...(includeQuerySourceCommunityId ? ['query_source_community_id'] : []),
      'link_surface',
      ...(includeCommunityTitle ? ['community_title'] : []),
      'entities_status',
      'relationships_status',
      'ancestors_status',
      'descendants_status',
    ],
    httpKeys: [
      'health',
      'query',
      ...(includeCommunityTitle ? ['community_detail'] : []),
      'entities',
      'relationships',
      'ancestors',
      'descendants',
    ],
  }
}

export function buildHighSignalCommunitySummaryRefreshSchemaCase({
  includeQueryCommunityIds = false,
  includeQuerySourceCommunityId = false,
} = {}) {
  return {
    summaryKeys: [
      'target_community_id',
      ...(includeQueryCommunityIds ? ['query_community_ids'] : []),
      ...(includeQuerySourceCommunityId ? ['query_source_community_id'] : []),
      'link_surface',
      'before_summary',
      'refreshed_summary',
      'entities_status',
      'relationships_status',
      'ancestors_status',
      'descendants_status',
    ],
    httpKeys: ['health', 'query', 'before_summary', 'entities', 'relationships', 'ancestors', 'descendants', 'after_summary'],
  }
}

export function buildHighSignalCommunityMissingDetailValueCase({
  linkSurface,
  includeQuerySourceCommunityId = false,
  includeQueryHitCommunityId = false,
} = {}) {
  return {
    patterns: [
      new RegExp(`link_surface:\\s*'${linkSurface}'`),
      ...(includeQuerySourceCommunityId ? [/query_source_community_id:\s*httpEvidence\.query\.json\?\.\s*sources\?\.\[0\]\?\.\s*community_id/] : []),
      ...(includeQueryHitCommunityId ? [/query_hit_community_id:\s*httpEvidence\.query\.json\?\.\s*communities\?\.\[0\]\?\.\s*community_id/] : []),
      /missing_detail_status:\s*httpEvidence\.missingCommunity\.statusCode/,
      /missing_detail:\s*\{\s*status_code:\s*httpEvidence\.missingCommunity\.statusCode,\s*body:\s*httpEvidence\.missingCommunity\.json,\s*\}/s,
    ],
  }
}

export function buildHighSignalCommunityDataFailureValueCase({
  linkSurface,
  includeQueryCommunityIds = false,
  includeQuerySourceCommunityId = false,
  includeCommunityTitle = false,
  includeCommunityDetailPattern = false,
  includeAncestorDescendantStatusPatterns = false,
  includeRelationshipsPattern = false,
} = {}) {
  return {
    patterns: [
      new RegExp(`link_surface:\\s*'${linkSurface}'`),
      ...(includeQueryCommunityIds ? [/query_community_ids:\s*\(httpEvidence\.query\.json\?\.communities\s*\|\|\s*\[\]\)\.map\(\(community\)\s*=>\s*community\.community_id\)/] : []),
      ...(includeQuerySourceCommunityId ? [/query_source_community_id:\s*httpEvidence\.query\.json\?\.\s*sources\?\.\[0\]\?\.\s*community_id/] : []),
      ...(includeCommunityTitle ? [/community_title:\s*httpEvidence\.communityDetail\.json\?\.title/] : []),
      /entities_status:\s*httpEvidence\.entities\.statusCode/,
      /relationships_status:\s*httpEvidence\.relationships\.statusCode/,
      ...(includeAncestorDescendantStatusPatterns ? [
        /ancestors_status:\s*httpEvidence\.ancestors\.statusCode/,
        /descendants_status:\s*httpEvidence\.descendants\.statusCode/,
      ] : []),
      ...(includeCommunityDetailPattern ? [/community_detail:\s*httpEvidence\.communityDetail\.json/] : []),
      /entities:\s*\{\s*status_code:\s*httpEvidence\.entities\.statusCode,\s*body:\s*httpEvidence\.entities\.json,\s*\}/s,
      ...(includeRelationshipsPattern ? [/relationships:\s*\{\s*status_code:\s*httpEvidence\.relationships\.statusCode,\s*body:\s*httpEvidence\.relationships\.json,\s*\}/s] : []),
    ],
  }
}

export function buildHighSignalCommunitySummaryRefreshValueCase({
  linkSurface,
  includeQueryCommunityIds = false,
  includeQuerySourceCommunityId = false,
  includeEntityRelationshipStatusPatterns = false,
} = {}) {
  return {
    patterns: [
      new RegExp(`link_surface:\\s*'${linkSurface}'`),
      ...(includeQueryCommunityIds ? [/query_community_ids:\s*\(httpEvidence\.query\.json\?\.communities\s*\|\|\s*\[\]\)\.map\(\(community\)\s*=>\s*community\.community_id\)/] : []),
      ...(includeQuerySourceCommunityId ? [/query_source_community_id:\s*httpEvidence\.query\.json\?\.\s*sources\?\.\[0\]\?\.\s*community_id/] : []),
      /before_summary:\s*httpEvidence\.beforeSummary\.json\?\.summary/,
      /refreshed_summary:\s*afterSummary\.json\?\.summary/,
      ...(includeEntityRelationshipStatusPatterns ? [
        /entities_status:\s*httpEvidence\.entities\.statusCode/,
        /relationships_status:\s*httpEvidence\.relationships\.statusCode/,
      ] : []),
      /after_summary:\s*afterSummary\.json/,
    ],
  }
}
