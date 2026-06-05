import {
  assertFocusedRealSmokeSchemaCase,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  buildCommunityDetailNavigationSchemaCase,
} from './focused-real-smoke-community-detail-navigation-contract-helpers.mjs'

function buildDashboardGraphSchemaCase({
  summaryKeys = [],
  httpKeys = ['health', 'stats', 'graph_entities', 'graph_relationships', 'recent_memories', 'communities'],
} = {}) {
  return {
    summaryKeys: [
      'navigation_surfaces',
      'total_entities',
      'total_relationships',
      'total_memories',
      ...summaryKeys,
    ],
    httpKeys,
  }
}

function buildDashboardCommunitiesSchemaCase({
  summaryKeys = [],
  httpKeys = ['health', 'stats', 'communities', 'hierarchy', 'recent_memories'],
} = {}) {
  return {
    summaryKeys: [
      'navigation_surface',
      'total_entities',
      'total_relationships',
      'total_memories',
      ...summaryKeys,
    ],
    httpKeys,
  }
}

function buildDashboardMemoriesSchemaCase({
  summaryKeys = [],
  httpKeys = ['health', 'stats', 'recent_memories', 'memories_list', 'communities'],
} = {}) {
  return {
    summaryKeys: [
      'navigation_surface',
      ...summaryKeys,
    ],
    httpKeys,
  }
}

function buildDashboardRecentMemoryDeleteFailureSchemaCase({
  summaryKeys = [],
  httpKeys = ['health', 'recent_before_delete', 'seeded_detail', 'delete', 'deleted_detail', 'deleted_context', 'recent_after_delete'],
} = {}) {
  return {
    summaryKeys: [
      'navigation_surface',
      'delete_status',
      'deleted_detail_status',
      'deleted_context_status',
      'recent_total_before_delete',
      'recent_total_after_delete',
      'refreshed_dashboard_empty',
      ...summaryKeys,
    ],
    httpKeys,
  }
}

function buildDashboardRecentMemoryWriteSchemaCase({
  summaryKeys = [],
  httpKeys = [
    'health',
    'recent_memories',
    'detail_before',
    'active_before',
    'archived_before',
    'detail_after_archive',
    'active_after_archive',
    'archived_after_archive',
    'detail_after_unarchive',
    'active_after_unarchive',
    'archived_after_unarchive',
    'delete',
    'detail_after_delete',
    'context_after_delete',
    'active_after_delete',
    'archived_after_delete',
    'all_after_delete',
  ],
} = {}) {
  return {
    summaryKeys: [
      'navigation_surface',
      'active_before',
      'archived_before',
      'active_after_archive',
      'archived_after_archive',
      'active_after_unarchive',
      'archived_after_unarchive',
      'active_after_delete',
      'archived_after_delete',
      'total_after_delete',
      'detail_status_after_delete',
      'context_status_after_delete',
      'refreshed_dashboard_empty',
      ...summaryKeys,
    ],
    httpKeys,
  }
}

export const DASHBOARD_SCHEMA_CASES_BY_TASK_ID = Object.freeze({
  'task-45': buildDashboardRecentMemoryDeleteFailureSchemaCase({
    summaryKeys: ['stale_recent_memory_id'],
  }),
  'task-46': buildDashboardRecentMemoryWriteSchemaCase({
    summaryKeys: ['recent_memory_id'],
  }),
  'task-47': buildCommunityDetailNavigationSchemaCase({
    summaryKeys: ['recent_memory_id', 'navigation_path'],
    includeRecentMemoriesHttp: true,
  }),
  'task-48': buildDashboardMemoriesSchemaCase({
    summaryKeys: ['profile', 'recent_memories_total', 'recent_memories_visible', 'active_list_total', 'active_list_visible'],
    httpKeys: ['health', 'recent_memories', 'memories_list'],
  }),
  'task-49': buildDashboardGraphSchemaCase({
    summaryKeys: ['total_communities', 'graph_entity_count', 'graph_relationship_count', 'memories_list_total'],
    httpKeys: ['health', 'stats', 'graph_entities', 'graph_relationships', 'memories', 'communities'],
  }),
  'task-50': buildDashboardGraphSchemaCase({
    summaryKeys: ['total_communities', 'graph_entity_count', 'graph_relationship_count'],
  }),
  'task-51': buildDashboardCommunitiesSchemaCase({
    summaryKeys: ['total_communities', 'hierarchy_total'],
  }),
  'task-52': buildDashboardMemoriesSchemaCase({
    summaryKeys: [
      'total_entities',
      'total_relationships',
      'total_memories',
      'recent_memories_total',
      'active_list_total',
      'total_communities',
    ],
  }),
  'task-53': buildDashboardMemoriesSchemaCase({
    summaryKeys: ['total_memories', 'recent_memories_status', 'active_list_status', 'error_detail'],
  }),
  'task-54': buildDashboardCommunitiesSchemaCase({
    summaryKeys: ['communities_list_status', 'hierarchy_status', 'list_error_detail', 'hierarchy_error_detail'],
  }),
  'task-55': buildDashboardGraphSchemaCase({
    summaryKeys: ['graph_entities_status', 'graph_relationships_status', 'entities_error_detail', 'relationships_error_detail'],
  }),
})

export function assertFocusedRealSmokeDashboardSchemaContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeSchemaCase(
    taskId,
    qaScriptFile,
    source,
    DASHBOARD_SCHEMA_CASES_BY_TASK_ID,
    'dashboard schema contract case'
  )
}
