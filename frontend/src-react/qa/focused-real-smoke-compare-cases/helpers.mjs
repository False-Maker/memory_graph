import assert from 'node:assert/strict'

import { getFocusedRealSmokeEvidenceFiles } from '../focused-real-smoke-task-registry.mjs'

export const QUERY_MODE_IDS = Object.freeze(['global', 'local', 'hybrid'])

export function createTaskCase(taskId, definition) {
  const evidenceFiles = getFocusedRealSmokeEvidenceFiles(taskId)
  assert.ok(evidenceFiles, `Missing focused smoke evidence files for ${taskId}`)
  return {
    ...evidenceFiles,
    ...definition,
  }
}

export function normalizeList(value, mapper = (item) => item) {
  return Array.isArray(value) ? value.map(mapper) : []
}

export function normalizeUrlPathAndHash(value) {
  if (typeof value !== 'string' || value.length === 0) return null
  try {
    const url = new URL(value)
    return `${url.pathname}${url.hash}`
  } catch {
    return value
  }
}

export function normalizeRouteWithIdPlaceholder(value, id) {
  const route = normalizeUrlPathAndHash(value)
  if (typeof route !== 'string' || typeof id !== 'string' || id.length === 0) {
    return route
  }
  return route.replace(id, ':id')
}

export function entityNames(items) {
  return normalizeList(items, (item) => item?.name).filter(Boolean)
}

export function itemTitles(items) {
  return normalizeList(items, (item) => item?.title).filter(Boolean)
}

export function normalizeQueryModeMap(queryModes, mapper = (value) => value) {
  return Object.fromEntries(
    QUERY_MODE_IDS.map((modeId) => [modeId, mapper(queryModes?.[modeId], modeId)])
  )
}

export function queryCommunityIds(query) {
  return normalizeList(query?.communities, (community) => community?.community_id).filter(Boolean)
}

export function queryCommunityTitles(query) {
  return normalizeList(query?.communities, (community) => community?.title).filter(Boolean)
}

export function querySourceCommunityIds(query) {
  return normalizeList(query?.sources, (source) => source?.community_id).filter(Boolean)
}

export function memoryTitles(items) {
  return normalizeList(items, (item) => item?.metadata?.title ?? item?.title).filter(Boolean)
}

export function memoryIds(items) {
  return normalizeList(items, (item) => item?.id).filter(Boolean)
}

export function relationshipTriples(relationships) {
  return normalizeList(relationships, (relationship) => ({
    source: relationship?.source ?? null,
    target: relationship?.target ?? null,
    type: relationship?.type ?? null,
  }))
}

export function normalizeMissingDetail(missingDetail) {
  return {
    status_code: missingDetail?.status_code ?? null,
    detail: missingDetail?.body?.detail ?? null,
  }
}

export function normalizeHealth(health) {
  return {
    status: health?.status ?? null,
    service: health?.service ?? null,
    version: health?.version ?? null,
    config_ok: health?.checks?.config?.ok ?? null,
    provider: health?.checks?.config?.provider ?? null,
    sqlite_ok: health?.checks?.sqlite?.ok ?? null,
    vector_store_ok: health?.checks?.vector_store?.ok ?? null,
    vector_dimension_mismatch: health?.checks?.vector_store?.state?.dimension_mismatch ?? null,
    vector_stored_documents: health?.checks?.vector_store?.state?.stored_documents ?? null,
  }
}

export function buildSearchCommunityMissingDetailNormalizer({
  includeQuerySourceMatch = false,
  includeQueryHitMatch = false,
  includeQueryAnswer = false,
  includeQueryCommunityIds = false,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    community_id: summary.community_id ?? null,
    missing_community_id: summary.missing_community_id ?? null,
    link_surface: summary.link_surface ?? null,
    missing_detail_status: summary.missing_detail_status ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    ...(includeQuerySourceMatch ? {
      query_source_matches_community: summary.query_source_community_id === summary.community_id,
    } : {}),
    ...(includeQueryHitMatch ? {
      query_hit_matches_community: summary.query_hit_community_id === summary.community_id,
    } : {}),
    health: normalizeHealth(http.health),
    ...(includeQueryAnswer ? { query_answer: http.query?.answer ?? null } : {}),
    ...(includeQueryCommunityIds ? { query_community_ids: queryCommunityIds(http.query) } : {}),
    query_titles: queryCommunityTitles(http.query),
    community_title: http.community_detail?.title ?? null,
    missing_detail: normalizeMissingDetail(http.missing_detail),
  })
}

export function buildSearchCommunityDataFailureNormalizer({
  includeQueryCommunityIds = false,
  includeQuerySourceCommunityIds = false,
  includeQuerySourceMatch = false,
  includeCommunityTitle = false,
  includeDetailTitle = false,
  includeAncestorTitles = false,
  includeDescendantTitles = false,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    target_community_id: summary.target_community_id ?? null,
    ...(includeQueryCommunityIds ? { query_community_ids: normalizeList(summary.query_community_ids) } : {}),
    link_surface: summary.link_surface ?? null,
    ...(includeCommunityTitle ? { community_title: summary.community_title ?? null } : {}),
    entities_status: summary.entities_status ?? null,
    relationships_status: summary.relationships_status ?? null,
    ancestors_status: summary.ancestors_status ?? null,
    descendants_status: summary.descendants_status ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    ...(includeQuerySourceMatch ? {
      query_source_matches_target: summary.query_source_community_id === summary.target_community_id,
    } : {}),
    health: normalizeHealth(http.health),
    query_titles: queryCommunityTitles(http.query),
    ...(includeQuerySourceCommunityIds ? { query_source_community_ids: querySourceCommunityIds(http.query) } : {}),
    ...(includeDetailTitle ? { detail_title: http.community_detail?.title ?? null } : {}),
    entities_error_detail: http.entities?.body?.detail ?? null,
    relationships_error_detail: http.relationships?.body?.detail ?? null,
    ...(includeAncestorTitles ? { ancestor_titles: itemTitles(http.ancestors?.ancestors) } : {}),
    ancestor_total: http.ancestors?.total ?? null,
    ...(includeDescendantTitles ? { descendant_titles: itemTitles(http.descendants?.descendants) } : {}),
    descendant_total: http.descendants?.total ?? null,
  })
}

export function buildSearchCommunitySummaryRefreshNormalizer({
  includeQueryCommunityIds = false,
  includeQuerySourceMatch = false,
  includeAncestorTitles = false,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    target_community_id: summary.target_community_id ?? null,
    ...(includeQueryCommunityIds ? { query_community_ids: normalizeList(summary.query_community_ids) } : {}),
    link_surface: summary.link_surface ?? null,
    before_summary: summary.before_summary ?? null,
    refreshed_summary: summary.refreshed_summary ?? null,
    summary_changed: summary.before_summary !== summary.refreshed_summary,
    entities_status: summary.entities_status ?? null,
    relationships_status: summary.relationships_status ?? null,
    ancestors_status: summary.ancestors_status ?? null,
    descendants_status: summary.descendants_status ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    ...(includeQuerySourceMatch ? {
      query_source_matches_target: summary.query_source_community_id === summary.target_community_id,
    } : {}),
    health: normalizeHealth(http.health),
    query_titles: queryCommunityTitles(http.query),
    before_title: http.before_summary?.title ?? null,
    after_title: http.after_summary?.title ?? null,
    entities_error_detail: http.entities?.body?.detail ?? null,
    relationships_error_detail: http.relationships?.body?.detail ?? null,
    ...(includeAncestorTitles ? { ancestor_titles: itemTitles(http.ancestors?.ancestors) } : {}),
    ancestor_total: http.ancestors?.total ?? null,
    descendant_total: http.descendants?.total ?? null,
  })
}

export function buildSuccessfulCommunitySummaryRefreshNormalizer({
  includeProfile = false,
  includeEntityCount = false,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    ...(includeProfile ? { profile: summary.profile ?? null } : {}),
    community_id: summary.community_id ?? null,
    initial_summary: summary.initial_summary ?? null,
    refreshed_summary: summary.refreshed_summary ?? null,
    summary_changed: summary.initial_summary !== summary.refreshed_summary,
    ...(includeEntityCount ? { entity_count: summary.entity_count ?? null } : {}),
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    before_title: http.before_summary?.title ?? null,
    regenerate_summary: http.regenerate?.summary ?? null,
    regenerate_token_count: http.regenerate?.token_count ?? null,
    after_summary: http.after_summary?.summary ?? null,
    community_id_consistent:
      summary.community_id === http.before_summary?.id
      && summary.community_id === http.after_summary?.id
      && summary.community_id === http.regenerate?.community_id,
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildSingleMemoryContextReadNormalizer({
  finalRouteResolver = (summary) => normalizeUrlPathAndHash(summary.final_url),
  getMemoryContent = () => null,
  getCommunityTitle = (http) => http.communities?.communities?.[0]?.title ?? null,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    final_route: finalRouteResolver(summary),
    health: normalizeHealth(http.health),
    community_title: getCommunityTitle(http),
    memory_content: getMemoryContent(http),
    memory_context_entity_names: entityNames(http.memory_context?.entities),
    memory_context_total_entities: http.memory_context?.total_entities ?? null,
    memory_context_total_communities: http.memory_context?.total_communities ?? null,
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildCommunityDetailNavigationNormalizer({
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    community_id: summary.community_id ?? null,
    memory_context_communities: summary.memory_context_communities ?? null,
    community_entities_total: summary.community_entities_total ?? null,
    community_relationships_total: summary.community_relationships_total ?? null,
    ancestors_total: summary.ancestors_total ?? null,
    descendants_total: summary.descendants_total ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    community_id_matches_detail: summary.community_id === http.community_detail?.id,
    memory_context_entity_names: entityNames(http.memory_context?.entities),
    community_title: http.community_detail?.title ?? null,
    community_summary: http.community_detail?.summary ?? null,
    community_entity_names: entityNames(http.community_entities?.entities),
    community_relationships: relationshipTriples(http.community_relationships?.relationships),
    ancestor_titles: itemTitles(http.community_ancestors?.ancestors),
    descendant_titles: itemTitles(http.community_descendants?.descendants),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildDashboardGraphStatsNormalizer({
  includeTotalCommunities = false,
  includeRecentMemoriesTotal = true,
  includeCommunitiesTotal = true,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    navigation_surfaces: normalizeList(summary.navigation_surfaces),
    total_entities: summary.total_entities ?? null,
    total_relationships: summary.total_relationships ?? null,
    total_memories: summary.total_memories ?? null,
    ...(includeTotalCommunities ? { total_communities: summary.total_communities ?? null } : {}),
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    entity_types: http.stats?.entity_types ?? {},
    ...(includeRecentMemoriesTotal ? { recent_memories_total: http.recent_memories?.total ?? null } : {}),
    ...(includeCommunitiesTotal ? { communities_total: http.communities?.total ?? null } : {}),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildDashboardCommunitiesStatsNormalizer({
  includeTotalCommunities = false,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    navigation_surface: summary.navigation_surface ?? null,
    total_entities: summary.total_entities ?? null,
    total_relationships: summary.total_relationships ?? null,
    total_memories: summary.total_memories ?? null,
    ...(includeTotalCommunities ? { total_communities: summary.total_communities ?? null } : {}),
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    entity_types: http.stats?.entity_types ?? {},
    recent_memories_total: http.recent_memories?.total ?? null,
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildDashboardMemoriesStatsNormalizer({
  includeTotalMemories = true,
  includeEntityRelationshipTotals = false,
  includeTotalCommunities = false,
  includeEntityTypes = true,
  includeCommunitiesTotal = true,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    navigation_surface: summary.navigation_surface ?? null,
    ...(includeEntityRelationshipTotals ? {
      total_entities: summary.total_entities ?? null,
      total_relationships: summary.total_relationships ?? null,
    } : {}),
    ...(includeTotalMemories ? { total_memories: summary.total_memories ?? null } : {}),
    ...(includeTotalCommunities ? { total_communities: summary.total_communities ?? null } : {}),
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    ...(includeEntityTypes ? { entity_types: http.stats?.entity_types ?? {} } : {}),
    ...(includeCommunitiesTotal ? { communities_total: http.communities?.total ?? null } : {}),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildDashboardRecentMemoryDeleteFailureNormalizer({
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    navigation_surface: summary.navigation_surface ?? null,
    delete_status: summary.delete_status ?? null,
    deleted_detail_status: summary.deleted_detail_status ?? null,
    deleted_context_status: summary.deleted_context_status ?? null,
    recent_total_before_delete: summary.recent_total_before_delete ?? null,
    recent_total_after_delete: summary.recent_total_after_delete ?? null,
    refreshed_dashboard_empty: summary.refreshed_dashboard_empty ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    stale_memory_matches_delete: summary.stale_recent_memory_id === http.delete?.body?.memory_id,
    recent_memory_titles_before_delete: memoryTitles(http.recent_before_delete?.memories),
    seeded_detail_title: http.seeded_detail?.metadata?.title ?? null,
    delete_success: http.delete?.body?.success ?? null,
    delete_message: http.delete?.body?.message ?? null,
    deleted_detail: normalizeMissingDetail(http.deleted_detail),
    deleted_context: normalizeMissingDetail(http.deleted_context),
    recent_memory_ids_after_delete: memoryIds(http.recent_after_delete?.memories),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildDashboardRecentMemoryWriteNormalizer({
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    navigation_surface: summary.navigation_surface ?? null,
    active_before: summary.active_before ?? null,
    archived_before: summary.archived_before ?? null,
    active_after_archive: summary.active_after_archive ?? null,
    archived_after_archive: summary.archived_after_archive ?? null,
    active_after_unarchive: summary.active_after_unarchive ?? null,
    archived_after_unarchive: summary.archived_after_unarchive ?? null,
    active_after_delete: summary.active_after_delete ?? null,
    archived_after_delete: summary.archived_after_delete ?? null,
    total_after_delete: summary.total_after_delete ?? null,
    detail_status_after_delete: summary.detail_status_after_delete ?? null,
    context_status_after_delete: summary.context_status_after_delete ?? null,
    refreshed_dashboard_empty: summary.refreshed_dashboard_empty ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    recent_memory_matches_detail:
      summary.recent_memory_id === http.recent_memories?.memories?.[0]?.id
      && summary.recent_memory_id === http.detail_before?.id,
    recent_titles: memoryTitles(http.recent_memories?.memories),
    active_titles_before: memoryTitles(http.active_before?.memories),
    archived_titles_before: memoryTitles(http.archived_before?.memories),
    detail_before_title: http.detail_before?.metadata?.title ?? null,
    detail_archived_after_archive: http.detail_after_archive?.metadata?.archived ?? null,
    detail_archived_after_unarchive: http.detail_after_unarchive?.metadata?.archived ?? null,
    delete_success: http.delete?.success ?? null,
    delete_message: http.delete?.message ?? null,
    delete_memory_id_matches_summary: http.delete?.memory_id === summary.recent_memory_id,
    detail_after_delete: normalizeMissingDetail(http.detail_after_delete),
    context_after_delete: normalizeMissingDetail(http.context_after_delete),
    active_titles_after_delete: memoryTitles(http.active_after_delete?.memories),
    archived_titles_after_delete: memoryTitles(http.archived_after_delete?.memories),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildRemainingWebMemoryWriteNormalizer({
  includeProfile = false,
  includeNavigationSurface = false,
  includeCommunityId = false,
  includeContextStatusAfterDelete = false,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    ...(includeProfile ? { profile: summary.profile ?? null } : {}),
    ...(includeNavigationSurface ? { navigation_surface: summary.navigation_surface ?? null } : {}),
    ...(includeCommunityId ? { community_id: summary.community_id ?? null } : {}),
    active_before: summary.active_before ?? null,
    archived_before: summary.archived_before ?? null,
    active_after_archive: summary.active_after_archive ?? null,
    archived_after_archive: summary.archived_after_archive ?? null,
    active_after_unarchive: summary.active_after_unarchive ?? null,
    archived_after_unarchive: summary.archived_after_unarchive ?? null,
    active_after_delete: summary.active_after_delete ?? null,
    archived_after_delete: summary.archived_after_delete ?? null,
    total_after_delete: summary.total_after_delete ?? null,
    detail_status_after_delete: summary.detail_status_after_delete ?? null,
    ...(includeContextStatusAfterDelete ? {
      context_status_after_delete: summary.context_status_after_delete ?? null,
    } : {}),
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    delete_success: http.delete?.success ?? null,
    delete_message: http.delete?.message ?? null,
    detail_after_delete: normalizeMissingDetail(http.detail_after_delete),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildRemainingWebMemoryDeleteFailureNormalizer({
  includeNavigationSurface = false,
  includeQuerySourceMatch = false,
  includeAfterDeleteStatusFields = true,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    ...(includeNavigationSurface ? { navigation_surface: summary.navigation_surface ?? null } : {}),
    ...(includeQuerySourceMatch ? {
      query_source_matches_recent: summary.recent_memory_id === summary.query_source_memory_id,
    } : {}),
    delete_status: summary.delete_status ?? null,
    ...(includeAfterDeleteStatusFields ? {
      detail_status_after_delete: summary.detail_status_after_delete ?? null,
      context_status_after_delete: summary.context_status_after_delete ?? null,
    } : {}),
    total_after_delete: summary.total_after_delete ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    delete_success: http.delete?.body?.success ?? null,
    delete_message: http.delete?.body?.message ?? null,
    detail_after_delete: normalizeMissingDetail(http.detail_after_delete),
    context_after_delete: normalizeMissingDetail(http.context_after_delete),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildRemainingWebCommunityFailureNormalizer({
  includeAncestorError = false,
  includeDescendantError = false,
  includeEntityError = false,
  includeRelationshipError = false,
  includeEntityData = false,
  includeRelationshipData = false,
  includeAncestorTitles = false,
  includeDescendantTitles = false,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    target_community_id: summary.target_community_id ?? null,
    ancestors_status: summary.ancestors_status ?? null,
    descendants_status: summary.descendants_status ?? null,
    entities_status: summary.entities_status ?? null,
    relationships_status: summary.relationships_status ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    community_title: http.community_detail?.title ?? null,
    ...(includeAncestorError ? { ancestors: normalizeMissingDetail(http.ancestors) } : {}),
    ...(includeDescendantError ? { descendants: normalizeMissingDetail(http.descendants) } : {}),
    ...(includeEntityError ? { entities: normalizeMissingDetail(http.entities) } : {}),
    ...(includeRelationshipError ? { relationships: normalizeMissingDetail(http.relationships) } : {}),
    ...(includeEntityData ? {
      entity_names: entityNames(http.entities?.entities),
      entity_total: http.entities?.total ?? null,
    } : {}),
    ...(includeRelationshipData ? {
      relationship_types: normalizeList(http.relationships?.relationships, (item) => item?.type).filter(Boolean),
      relationship_total: http.relationships?.total ?? null,
    } : {}),
    ...(includeAncestorTitles ? {
      ancestor_titles: itemTitles(http.ancestors?.ancestors),
      ancestor_total: http.ancestors?.total ?? null,
    } : {}),
    ...(includeDescendantTitles ? {
      descendant_titles: itemTitles(http.descendants?.descendants),
      descendant_total: http.descendants?.total ?? null,
    } : {}),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}

export function buildRemainingWebCommunitySummaryRefreshNormalizer({
  includeAncestorTitles = false,
  includeDescendantTitles = false,
  customNormalize,
} = {}) {
  return ({ summary, http }) => ({
    command: summary.command ?? null,
    status: summary.status ?? null,
    target_community_id: summary.target_community_id ?? null,
    before_summary: summary.before_summary ?? null,
    refreshed_summary: summary.refreshed_summary ?? null,
    summary_changed: summary.before_summary !== summary.refreshed_summary,
    entities_status: summary.entities_status ?? null,
    relationships_status: summary.relationships_status ?? null,
    ancestors_status: summary.ancestors_status ?? null,
    descendants_status: summary.descendants_status ?? null,
    final_route: normalizeUrlPathAndHash(summary.final_url),
    health: normalizeHealth(http.health),
    before_title: http.before_summary?.title ?? null,
    after_title: http.after_summary?.title ?? null,
    entities: normalizeMissingDetail(http.entities),
    relationships: normalizeMissingDetail(http.relationships),
    ...(includeAncestorTitles ? {
      ancestor_titles: itemTitles(http.ancestors?.ancestors),
      ancestor_total: http.ancestors?.total ?? null,
    } : {}),
    ...(includeDescendantTitles ? {
      descendant_titles: itemTitles(http.descendants?.descendants),
      descendant_total: http.descendants?.total ?? null,
    } : {
      descendant_total: http.descendants?.total ?? null,
    }),
    ...(customNormalize ? customNormalize({ summary, http }) : {}),
  })
}
