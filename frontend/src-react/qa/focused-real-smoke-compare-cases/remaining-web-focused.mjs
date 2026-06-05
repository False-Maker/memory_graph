import {
  buildRemainingWebCommunityFailureNormalizer,
  buildRemainingWebCommunitySummaryRefreshNormalizer,
  buildRemainingWebMemoryDeleteFailureNormalizer,
  buildRemainingWebMemoryWriteNormalizer,
  buildSuccessfulCommunitySummaryRefreshNormalizer,
  createTaskCase,
  entityNames,
  itemTitles,
  memoryTitles,
  normalizeHealth,
  normalizeList,
  normalizeMissingDetail,
  normalizeQueryModeMap,
  normalizeUrlPathAndHash,
  queryCommunityIds,
  queryCommunityTitles,
  querySourceCommunityIds,
  relationshipTriples,
} from './helpers.mjs'

export const REMAINING_WEB_FOCUSED_TASK_CASES = {
  'task-26': createTaskCase('task-26', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        total_entities: summary.total_entities ?? null,
        total_relationships: summary.total_relationships ?? null,
        total_memories: summary.total_memories ?? null,
        browser_node_count: summary.browser_node_count ?? null,
        final_route: normalizeUrlPathAndHash(summary.final_url),
        health: normalizeHealth(http.health),
        entity_types: http.stats?.entity_types ?? {},
        entity_names: entityNames(http.entities?.entities),
        relationship_types: normalizeList(http.relationships?.relationships, (item) => item?.type).filter(Boolean),
        relationship_total: http.relationships?.total ?? null,
      }
    },
  }),
  'task-29': createTaskCase('task-29', {
    normalize: buildSuccessfulCommunitySummaryRefreshNormalizer({
      includeProfile: true,
      includeEntityCount: true,
      customNormalize: ({ summary }) => ({
        fake_ollama_generate_requests: summary.fake_ollama_generate_requests ?? null,
      }),
    }),
  }),
  'task-30': createTaskCase('task-30', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        profile: summary.profile ?? null,
        community_ids: normalizeList(summary.community_ids),
        total_entities: summary.total_entities ?? null,
        total_relationships: summary.total_relationships ?? null,
        total_memories: summary.total_memories ?? null,
        total_communities: summary.total_communities ?? null,
        hierarchy_root_id: summary.hierarchy_root_id ?? null,
        ancestor_total: summary.ancestor_total ?? null,
        returned_memory_count: normalizeList(summary.returned_memory_ids).length,
        recent_item_navigation: summary.recent_item_navigation ?? null,
        recent_memory_context_communities: summary.recent_memory_context_communities ?? null,
        community_link_surface: summary.community_link_surface ?? null,
        browser_memory_source_count: summary.browser_memory_source_count ?? null,
        browser_community_source_count: summary.browser_community_source_count ?? null,
        final_route: normalizeUrlPathAndHash(summary.final_url),
        recent_memory_matches_detail: summary.recent_memory_id === http.memory_detail?.id,
        health: normalizeHealth(http.health),
        entity_types: http.stats?.entity_types ?? {},
        communities_titles: itemTitles(http.communities?.communities),
        memories_titles: memoryTitles(http.memories?.memories),
        recent_memory_title: http.memory_detail?.metadata?.title ?? null,
        memory_context_community_titles: itemTitles(http.memory_context?.communities),
        query_source_titles: memoryTitles(http.query?.sources),
        query_community_titles: queryCommunityTitles(http.query),
      }
    },
  }),
  'task-31': createTaskCase('task-31', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        profile: summary.profile ?? null,
        total_memories: summary.total_memories ?? null,
        active_total: summary.active_total ?? null,
        archived_total: summary.archived_total ?? null,
        page1_count: summary.page1_count ?? null,
        page2_count: summary.page2_count ?? null,
        final_route: normalizeUrlPathAndHash(summary.final_url),
        health: normalizeHealth(http.health),
        active_titles: memoryTitles(http.active?.memories),
        archived_titles: memoryTitles(http.archived?.memories),
        all_page_1_titles: memoryTitles(http.all_page_1?.memories),
        all_page_2_titles: memoryTitles(http.all_page_2?.memories),
      }
    },
  }),
  'task-32': createTaskCase('task-32', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        total_communities: summary.total_communities ?? null,
        hierarchy_total: summary.hierarchy_total ?? null,
        root_id: summary.root_id ?? null,
        ancestors_total: summary.ancestors_total ?? null,
        descendants_total: summary.descendants_total ?? null,
        final_route: normalizeUrlPathAndHash(summary.final_url),
        health: normalizeHealth(http.health),
        communities_titles: itemTitles(http.communities?.communities),
        hierarchy_root_titles: itemTitles(http.hierarchy?.roots),
        hierarchy_root_child_titles: itemTitles(http.hierarchy?.roots?.[0]?.children),
        subtree_title: http.subtree?.title ?? null,
        ancestor_titles: itemTitles(http.ancestors?.ancestors),
        descendant_titles: itemTitles(http.descendants?.descendants),
      }
    },
  }),
  'task-33': createTaskCase('task-33', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        delete_status: summary.delete_status ?? null,
        detail_status_after_delete: summary.detail_status_after_delete ?? null,
        final_route: normalizeUrlPathAndHash(summary.final_url),
        health: normalizeHealth(http.health),
        query_answer: http.query?.answer ?? null,
        query_source_titles: memoryTitles(http.query?.sources),
        query_source_community_ids: querySourceCommunityIds(http.query),
        delete_status_http: http.deleted?.status_code ?? null,
        detail_after_delete_status_http: http.detail_after_delete?.status_code ?? null,
      }
    },
  }),
  'task-34': createTaskCase('task-34', {
    normalize: buildRemainingWebMemoryWriteNormalizer({
      includeProfile: true,
      customNormalize: ({ http }) => ({
        archive_target_id: http.archiveTargetId ?? null,
        delete_target_id: http.deleteTargetId ?? null,
        active_before_titles: memoryTitles(http.active_before?.memories),
        archived_before_titles: memoryTitles(http.archived_before?.memories),
        archive_success: http.archive?.success ?? null,
        archive_message: http.archive?.message ?? null,
        unarchive_success: http.unarchive?.success ?? null,
        unarchive_message: http.unarchive?.message ?? null,
        active_after_delete_titles: memoryTitles(http.active_after_delete?.memories),
        archived_after_delete_titles: memoryTitles(http.archived_after_delete?.memories),
      }),
    }),
  }),
  'task-35': createTaskCase('task-35', {
    normalize: buildRemainingWebMemoryWriteNormalizer({
      includeCommunityId: true,
      includeContextStatusAfterDelete: true,
      customNormalize: ({ summary, http }) => ({
        memory_id_matches_detail: summary.memory_id === http.memory_detail_before?.id,
        community_id_matches_context: summary.community_id === http.memory_context_before?.communities?.[0]?.id,
        memory_detail_title_before: http.memory_detail_before?.metadata?.title ?? null,
        memory_context_entity_names: entityNames(http.memory_context_before?.entities),
        memory_context_community_titles: itemTitles(http.memory_context_before?.communities),
        archive_success: http.archive?.success ?? null,
        archive_message: http.archive?.message ?? null,
        detail_archived_after_archive: http.detail_after_archive?.metadata?.archived ?? null,
        unarchive_success: http.unarchive?.success ?? null,
        unarchive_message: http.unarchive?.message ?? null,
        detail_archived_after_unarchive: http.detail_after_unarchive?.metadata?.archived ?? null,
        context_after_delete: normalizeMissingDetail(http.context_after_delete),
      }),
    }),
  }),
  'task-36': createTaskCase('task-36', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        community_id: summary.community_id ?? null,
        query_modes_tested: normalizeList(summary.query_modes_tested),
        global_query_source_memory_id: summary.global_query_source_memory_id ?? null,
        local_query_source_memory_id: summary.local_query_source_memory_id ?? null,
        hybrid_query_source_memory_id: summary.hybrid_query_source_memory_id ?? null,
        link_surface: summary.link_surface ?? null,
        memory_detail_requests: summary.memory_detail_requests ?? null,
        memory_link_count: summary.memory_link_count ?? null,
        final_route: normalizeUrlPathAndHash(summary.final_url),
        health: normalizeHealth(http.health),
        memories_total: http.memories?.total ?? null,
        communities_total: http.communities?.total ?? null,
        community_title: http.community_detail?.title ?? null,
        query_answers: normalizeQueryModeMap({
          global: http.query_global,
          local: http.query_local,
          hybrid: http.query_hybrid,
        }, (query) => query?.answer ?? null),
        query_community_ids: normalizeQueryModeMap({
          global: http.query_global,
          local: http.query_local,
          hybrid: http.query_hybrid,
        }, (query) => queryCommunityIds(query)),
        fake_ollama_counts: http.fake_ollama_counts ?? {},
      }
    },
  }),
  'task-37': createTaskCase('task-37', {
    normalize: buildRemainingWebMemoryDeleteFailureNormalizer({
      includeAfterDeleteStatusFields: false,
      customNormalize: ({ summary, http }) => ({
        missing_memory_id: summary.missing_memory_id ?? null,
        missing_detail_status: summary.missing_detail_status ?? null,
        missing_context_status: summary.missing_context_status ?? null,
        deleted_detail_status: summary.deleted_detail_status ?? null,
        deleted_context_status: summary.deleted_context_status ?? null,
        total_before_delete: summary.total_before_delete ?? null,
        seeded_memory_matches_delete: summary.seeded_memory_id === http.delete?.body?.memory_id,
        seeded_detail_title: http.seeded_detail?.metadata?.title ?? null,
        missing_detail: normalizeMissingDetail(http.missing_detail),
        missing_context: normalizeMissingDetail(http.missing_context),
        all_before_titles: memoryTitles(http.all_before_delete?.memories),
        deleted_detail: normalizeMissingDetail(http.deleted_detail),
        deleted_context: normalizeMissingDetail(http.deleted_context),
        all_after_titles: memoryTitles(http.all_after_delete?.memories),
      }),
    }),
  }),
  'task-38': createTaskCase('task-38', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        existing_community_id: summary.existing_community_id ?? null,
        missing_community_id: summary.missing_community_id ?? null,
        missing_detail_status: summary.missing_detail_status ?? null,
        total_communities: summary.total_communities ?? null,
        final_route: normalizeUrlPathAndHash(summary.final_url),
        health: normalizeHealth(http.health),
        communities_titles: itemTitles(http.communities?.communities),
        existing_community_present: normalizeList(http.communities?.communities, (item) => item?.id).includes(summary.existing_community_id),
        missing_detail: normalizeMissingDetail(http.missing_detail),
      }
    },
  }),
  'task-40': createTaskCase('task-40', {
    normalize: buildRemainingWebCommunityFailureNormalizer({
      includeAncestorError: true,
      includeDescendantError: true,
      includeEntityData: true,
      includeRelationshipData: true,
    }),
  }),
  'task-41': createTaskCase('task-41', {
    normalize: buildRemainingWebCommunityFailureNormalizer({
      includeEntityError: true,
      includeRelationshipError: true,
      includeAncestorTitles: true,
      includeDescendantTitles: true,
    }),
  }),
  'task-43': createTaskCase('task-43', {
    normalize: buildRemainingWebCommunitySummaryRefreshNormalizer({
      includeAncestorTitles: true,
    }),
  }),
  'task-56': createTaskCase('task-56', {
    normalize: buildRemainingWebMemoryWriteNormalizer({
      includeNavigationSurface: true,
      includeContextStatusAfterDelete: true,
      customNormalize: ({ summary, http }) => ({
        query_source_matches_recent: summary.recent_memory_id === summary.query_source_memory_id,
        query_answer: http.query?.answer ?? null,
        query_source_titles: memoryTitles(http.query?.sources),
        memory_detail_title: http.memory_detail?.metadata?.title ?? null,
        memory_context_entity_names: entityNames(http.memory_context?.entities),
        archive_success: http.detail_after_archive?.metadata?.archived ?? null,
        unarchive_success: http.detail_after_unarchive?.metadata?.archived === false,
        delete_memory_matches_recent: http.delete?.memory_id === summary.recent_memory_id,
        context_after_delete: normalizeMissingDetail(http.context_after_delete),
      }),
    }),
  }),
  'task-57': createTaskCase('task-57', {
    normalize: buildRemainingWebMemoryDeleteFailureNormalizer({
      includeNavigationSurface: true,
      includeQuerySourceMatch: true,
      customNormalize: ({ summary, http }) => ({
        query_answer: http.query?.answer ?? null,
        query_source_titles: memoryTitles(http.query?.sources),
        delete_memory_matches_recent: http.delete?.body?.memory_id === summary.recent_memory_id,
        all_after_titles: memoryTitles(http.all_after_delete?.memories),
      }),
    }),
  }),
}
