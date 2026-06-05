import { assertFocusedRealSmokeValueCase } from './focused-real-smoke-contract-helpers.mjs'
import {
  buildCommunityDetailNavigationValueCase,
} from './focused-real-smoke-community-detail-navigation-contract-helpers.mjs'

function buildDashboardGraphValueCase({
  patterns = [],
  tailPatterns = [
    /graph_entities:\s*httpEvidence\.graphEntities\.json/,
    /graph_relationships:\s*httpEvidence\.graphRelationships\.json/,
    /recent_memories:\s*httpEvidence\.recentMemories\.json/,
    /communities:\s*httpEvidence\.communities\.json/,
  ],
} = {}) {
  return {
    patterns: [
      ...patterns,
      ...tailPatterns,
    ],
  }
}

function buildDashboardCommunitiesValueCase({
  patterns = [],
  tailPatterns = [
    /communities:\s*httpEvidence\.communities\.json/,
    /hierarchy:\s*httpEvidence\.hierarchy\.json/,
    /recent_memories:\s*httpEvidence\.recentMemories\.json/,
  ],
} = {}) {
  return {
    patterns: [
      ...patterns,
      ...tailPatterns,
    ],
  }
}

function buildDashboardMemoriesValueCase({
  patterns = [],
  tailPatterns = [
    /recent_memories:\s*httpEvidence\.recentMemories\.json/,
    /memories_list:\s*httpEvidence\.memoriesList\.json/,
    /communities:\s*httpEvidence\.communities\.json/,
  ],
} = {}) {
  return {
    patterns: [
      ...patterns,
      ...tailPatterns,
    ],
  }
}

function buildDashboardRecentMemoryDeleteFailureValueCase({
  patterns = [],
  tailPatterns = [
    /deleted_detail:\s*\{\s*status_code:\s*browserEvidence\.deletedDetail\.statusCode,\s*body:\s*browserEvidence\.deletedDetail\.json,\s*\}/s,
    /deleted_context:\s*\{\s*status_code:\s*browserEvidence\.deletedContext\.statusCode,\s*body:\s*browserEvidence\.deletedContext\.json,\s*\}/s,
  ],
} = {}) {
  return {
    patterns: [
      /navigation_surface:\s*'dashboard_recent_item'/,
      /delete_status:\s*browserEvidence\.deleteResponse\.statusCode/,
      /deleted_detail_status:\s*browserEvidence\.deletedDetail\.statusCode/,
      /recent_total_before_delete:\s*httpEvidence\.recentBeforeDelete\.json\?\.total/,
      /recent_total_after_delete:\s*browserEvidence\.recentAfterDelete\.json\?\.total/,
      ...patterns,
      ...tailPatterns,
    ],
  }
}

function buildDashboardRecentMemoryWriteValueCase({
  patterns = [],
  tailPatterns = [
    /detail_after_archive:\s*browserEvidence\.detailAfterArchive\.json/,
    /detail_after_unarchive:\s*browserEvidence\.detailAfterUnarchive\.json/,
    /delete:\s*browserEvidence\.deletePayload/,
  ],
} = {}) {
  return {
    patterns: [
      /navigation_surface:\s*'dashboard_recent_item'/,
      /active_before:\s*httpEvidence\.activeBefore\.json\?\.total/,
      /archived_after_archive:\s*browserEvidence\.archivedAfterArchive\.json\?\.total/,
      /detail_status_after_delete:\s*browserEvidence\.detailAfterDelete\.statusCode/,
      /context_status_after_delete:\s*browserEvidence\.contextAfterDelete\.statusCode/,
      ...patterns,
      ...tailPatterns,
    ],
  }
}

export const DASHBOARD_VALUE_CASES_BY_TASK_ID = Object.freeze({
  'task-45': buildDashboardRecentMemoryDeleteFailureValueCase(),
  'task-46': buildDashboardRecentMemoryWriteValueCase(),
  'task-47': buildCommunityDetailNavigationValueCase({
    patterns: [
      /recent_memory_id:\s*seedPayload\.memory_id/,
      /navigation_path:\s*'dashboard_recent_item,memory_detail,community_detail'/,
    ],
    tailPatterns: [
      /recent_memories:\s*httpEvidence\.recentMemories\.json/,
      /memory_context_communities:\s*httpEvidence\.memoryContext\.json\?\.total_communities/,
      /community_entities_total:\s*httpEvidence\.communityEntities\.json\?\.total/,
      /community_relationships_total:\s*httpEvidence\.communityRelationships\.json\?\.total/,
      /community_relationships:\s*httpEvidence\.communityRelationships\.json/,
      /community_ancestors:\s*httpEvidence\.ancestors\.json/,
      /community_descendants:\s*httpEvidence\.descendants\.json/,
    ],
  }),
  'task-48': buildDashboardMemoriesValueCase({
    patterns: [
      /profile:\s*'memories_list'/,
      /navigation_surface:\s*'dashboard_view_all'/,
      /recent_memories_total:\s*httpEvidence\.recentMemories\.json\?\.total/,
      /recent_memories_visible:\s*httpEvidence\.recentMemories\.json\?\.memories\?\.length/,
      /active_list_total:\s*httpEvidence\.memoriesList\.json\?\.total/,
      /active_list_visible:\s*httpEvidence\.memoriesList\.json\?\.memories\?\.length/,
    ],
    tailPatterns: [
      /recent_memories:\s*httpEvidence\.recentMemories\.json/,
      /memories_list:\s*httpEvidence\.memoriesList\.json/,
    ],
  }),
  'task-49': buildDashboardGraphValueCase({
    patterns: [
      /navigation_surfaces:\s*\[\s*'entities->graph',\s*'relationships->graph',\s*'memories->memories',\s*'communities->communities',\s*\]/s,
      /graph_entity_count:\s*httpEvidence\.graphEntities\.json\?\.entities\?\.length/,
      /graph_relationship_count:\s*httpEvidence\.graphRelationships\.json\?\.relationships\?\.length/,
      /memories_list_total:\s*httpEvidence\.memories\.json\?\.total/,
    ],
    tailPatterns: [
      /graph_entities:\s*httpEvidence\.graphEntities\.json/,
      /graph_relationships:\s*httpEvidence\.graphRelationships\.json/,
      /memories:\s*httpEvidence\.memories\.json/,
      /communities:\s*httpEvidence\.communities\.json/,
    ],
  }),
  'task-50': buildDashboardGraphValueCase({
    patterns: [
      /navigation_surfaces:\s*\['entities->graph_empty', 'relationships->graph_empty'\]/,
      /graph_entity_count:\s*httpEvidence\.graphEntities\.json\?\.total/,
      /graph_relationship_count:\s*httpEvidence\.graphRelationships\.json\?\.total/,
    ],
  }),
  'task-51': buildDashboardCommunitiesValueCase({
    patterns: [
      /navigation_surface:\s*'communities->communities_empty'/,
      /total_communities:\s*httpEvidence\.communities\.json\?\.total/,
      /hierarchy_total:\s*httpEvidence\.hierarchy\.json\?\.total_communities/,
    ],
  }),
  'task-52': buildDashboardMemoriesValueCase({
    patterns: [
      /navigation_surface:\s*'memories->memories_empty'/,
      /recent_memories_total:\s*httpEvidence\.recentMemories\.json\?\.total/,
      /active_list_total:\s*httpEvidence\.memoriesList\.json\?\.total/,
    ],
  }),
  'task-53': buildDashboardMemoriesValueCase({
    patterns: [
      /navigation_surface:\s*'memories->memories_failure'/,
      /recent_memories_status:\s*httpEvidence\.memoriesRecent\.statusCode/,
      /active_list_status:\s*httpEvidence\.memoriesList\.statusCode/,
      /error_detail:\s*httpEvidence\.memoriesList\.json\?\.detail/,
    ],
    tailPatterns: [
      /recent_memories:\s*\{\s*status_code:\s*httpEvidence\.memoriesRecent\.statusCode,\s*body:\s*httpEvidence\.memoriesRecent\.json,\s*\}/s,
      /memories_list:\s*\{\s*status_code:\s*httpEvidence\.memoriesList\.statusCode,\s*body:\s*httpEvidence\.memoriesList\.json,\s*\}/s,
      /communities:\s*httpEvidence\.communities\.json/,
    ],
  }),
  'task-54': buildDashboardCommunitiesValueCase({
    patterns: [
      /navigation_surface:\s*'communities->communities_failure'/,
      /communities_list_status:\s*httpEvidence\.communities\.statusCode/,
      /hierarchy_status:\s*httpEvidence\.hierarchy\.statusCode/,
      /list_error_detail:\s*httpEvidence\.communities\.json\?\.detail/,
      /hierarchy_error_detail:\s*httpEvidence\.hierarchy\.json\?\.detail/,
    ],
    tailPatterns: [
      /communities:\s*\{\s*status_code:\s*httpEvidence\.communities\.statusCode,\s*body:\s*httpEvidence\.communities\.json,\s*\}/s,
      /hierarchy:\s*\{\s*status_code:\s*httpEvidence\.hierarchy\.statusCode,\s*body:\s*httpEvidence\.hierarchy\.json,\s*\}/s,
      /recent_memories:\s*httpEvidence\.recentMemories\.json/,
    ],
  }),
  'task-55': buildDashboardGraphValueCase({
    patterns: [
      /navigation_surfaces:\s*\['entities->graph_failure', 'relationships->graph_failure'\]/,
      /graph_entities_status:\s*httpEvidence\.graphEntities\.statusCode/,
      /graph_relationships_status:\s*httpEvidence\.graphRelationships\.statusCode/,
      /entities_error_detail:\s*httpEvidence\.graphEntities\.json\?\.detail/,
      /relationships_error_detail:\s*httpEvidence\.graphRelationships\.json\?\.detail/,
    ],
    tailPatterns: [
      /graph_entities:\s*\{\s*status_code:\s*httpEvidence\.graphEntities\.statusCode,\s*body:\s*httpEvidence\.graphEntities\.json,\s*\}/s,
      /graph_relationships:\s*\{\s*status_code:\s*httpEvidence\.graphRelationships\.statusCode,\s*body:\s*httpEvidence\.graphRelationships\.json,\s*\}/s,
      /recent_memories:\s*httpEvidence\.recentMemories\.json/,
      /communities:\s*httpEvidence\.communities\.json/,
    ],
  }),
})

export function assertFocusedRealSmokeDashboardValueContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeValueCase(taskId, qaScriptFile, source, DASHBOARD_VALUE_CASES_BY_TASK_ID, {
    missingCaseLabel: 'dashboard value contract case',
    missingBindingLabel: 'expected dashboard evidence binding',
  })
}
