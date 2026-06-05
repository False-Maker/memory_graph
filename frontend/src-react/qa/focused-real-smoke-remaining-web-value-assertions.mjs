import { assertFocusedRealSmokeValueCase } from './focused-real-smoke-contract-helpers.mjs'
import {
  buildSuccessfulCommunitySummaryRefreshValueCase,
} from './focused-real-smoke-community-summary-refresh-contract-helpers.mjs'

function buildRemainingWebMemoryWriteValueCase({
  patterns = [],
  includeArchiveDetailPatterns = false,
  tailPatterns = [],
} = {}) {
  return {
    patterns: [
      /active_before:\s*httpEvidence\.activeBefore\.json\?\.total/,
      ...patterns,
      ...(includeArchiveDetailPatterns ? [
        /detail_after_archive:\s*browserEvidence\.detailAfterArchive\.json/,
        /detail_after_unarchive:\s*browserEvidence\.detailAfterUnarchive\.json/,
      ] : []),
      /delete:\s*browserEvidence\.deletePayload/,
      /detail_after_delete:\s*\{\s*status_code:\s*browserEvidence\.detailAfterDelete\.statusCode,\s*body:\s*browserEvidence\.detailAfterDelete\.json,\s*\}/s,
      ...tailPatterns,
    ],
  }
}

function buildRemainingWebMemoryDeleteFailureValueCase({
  patterns = [],
  includeAfterDeleteStatusPatterns = true,
  detailObjectPattern = /detail_after_delete:\s*\{\s*status_code:\s*browserEvidence\.detailAfterDelete\.statusCode,\s*body:\s*browserEvidence\.detailAfterDelete\.json,\s*\}/s,
  contextObjectPattern = /context_after_delete:\s*\{\s*status_code:\s*browserEvidence\.contextAfterDelete\.statusCode,\s*body:\s*browserEvidence\.contextAfterDelete\.json,\s*\}/s,
  tailPatterns = [
    /delete:\s*\{\s*status_code:\s*browserEvidence\.deleteResponse\.statusCode,\s*body:\s*browserEvidence\.deleteResponse\.json,\s*\}/s,
    /all_after_delete:\s*browserEvidence\.allAfterDelete\.json/,
  ],
} = {}) {
  return {
    patterns: [
      /delete_status:\s*browserEvidence\.deleteResponse\.statusCode/,
      ...(includeAfterDeleteStatusPatterns ? [
        /detail_status_after_delete:\s*browserEvidence\.detailAfterDelete\.statusCode/,
        /context_status_after_delete:\s*browserEvidence\.contextAfterDelete\.statusCode/,
      ] : []),
      ...patterns,
      detailObjectPattern,
      contextObjectPattern,
      ...tailPatterns,
    ],
  }
}

function buildRemainingWebCommunityFailureValueCase({
  patterns = [],
  tailPatterns = [
    /community_detail:\s*httpEvidence\.communityDetail\.json/,
    /ancestors:\s*httpEvidence\.ancestors\.json/,
    /descendants:\s*httpEvidence\.descendants\.json/,
    /entities:\s*httpEvidence\.entities\.json/,
    /relationships:\s*httpEvidence\.relationships\.json/,
  ],
} = {}) {
  return {
    patterns: [
      /target_community_id:\s*TARGET_COMMUNITY_ID/,
      /ancestors_status:\s*httpEvidence\.ancestors\.statusCode/,
      /descendants_status:\s*httpEvidence\.descendants\.statusCode/,
      /entities_status:\s*httpEvidence\.entities\.statusCode/,
      /relationships_status:\s*httpEvidence\.relationships\.statusCode/,
      ...patterns,
      ...tailPatterns,
    ],
  }
}

function buildRemainingWebCommunitySummaryRefreshValueCase({
  patterns = [],
  tailPatterns = [
    /before_summary:\s*httpEvidence\.beforeSummary\.json/,
    /entities:\s*\{\s*status_code:\s*httpEvidence\.entities\.statusCode,\s*body:\s*httpEvidence\.entities\.json,\s*\}/s,
    /relationships:\s*\{\s*status_code:\s*httpEvidence\.relationships\.statusCode,\s*body:\s*httpEvidence\.relationships\.json,\s*\}/s,
    /ancestors:\s*httpEvidence\.ancestors\.json/,
    /descendants:\s*httpEvidence\.descendants\.json/,
    /after_summary:\s*afterSummary\.json/,
  ],
} = {}) {
  return {
    patterns: [
      /target_community_id:\s*TARGET_COMMUNITY_ID/,
      /before_summary:\s*httpEvidence\.beforeSummary\.json\?\.summary/,
      /refreshed_summary:\s*afterSummary\.json\?\.summary/,
      /entities_status:\s*httpEvidence\.entities\.statusCode/,
      /relationships_status:\s*httpEvidence\.relationships\.statusCode/,
      /ancestors_status:\s*httpEvidence\.ancestors\.statusCode/,
      /descendants_status:\s*httpEvidence\.descendants\.statusCode/,
      ...patterns,
      ...tailPatterns,
    ],
  }
}

export const REMAINING_WEB_VALUE_CASES_BY_TASK_ID = Object.freeze({
  'task-26': {
    patterns: [
      /total_entities:\s*httpEvidence\.stats\.json\?\.total_entities/,
      /total_relationships:\s*httpEvidence\.stats\.json\?\.total_relationships/,
      /browser_node_count:\s*browserEvidence\.nodeCount/,
      /entities:\s*httpEvidence\.entities\.json/,
      /relationships:\s*httpEvidence\.relationships\.json/,
    ],
  },
  'task-29': buildSuccessfulCommunitySummaryRefreshValueCase({
    patterns: [
      /profile:\s*seedPayload\.profile/,
      /entity_count:\s*httpEvidence\.beforeSummary\.json\?\.entity_count/,
      /fake_ollama_generate_requests:\s*httpEvidence\.counts\.generateRequests/,
    ],
  }),
  'task-30': {
    patterns: [
      /profile:\s*seedPayload\.profile/,
      /memory_ids:\s*seedPayload\.memory_ids/,
      /community_ids:\s*seedPayload\.community_ids/,
      /hierarchy_root_id:\s*httpEvidence\.hierarchyRoot\?\.id/,
      /recent_item_navigation:\s*'memory_detail'/,
      /community_link_surface:\s*'result'/,
      /memory_detail:\s*httpEvidence\.memoryDetail\.json/,
      /memory_context:\s*httpEvidence\.memoryContext\.json/,
      /query:\s*httpEvidence\.query\.json/,
    ],
  },
  'task-31': {
    patterns: [
      /profile:\s*seedPayload\.profile/,
      /total_memories:\s*httpEvidence\.allPage1\.json\?\.total/,
      /active_total:\s*httpEvidence\.active\.json\?\.total/,
      /archived_total:\s*httpEvidence\.archived\.json\?\.total/,
      /all_page_1:\s*httpEvidence\.allPage1\.json/,
      /all_page_2:\s*httpEvidence\.allPage2\.json/,
    ],
  },
  'task-32': {
    patterns: [
      /total_communities:\s*httpEvidence\.communities\.json\?\.total/,
      /hierarchy_total:\s*httpEvidence\.hierarchy\.json\?\.total_communities/,
      /root_id:\s*httpEvidence\.root\.id/,
      /subtree:\s*httpEvidence\.subtree\.json/,
      /ancestors:\s*httpEvidence\.ancestors\.json/,
      /descendants:\s*httpEvidence\.descendants\.json/,
    ],
  },
  'task-33': {
    patterns: [
      /memory_id:\s*seedPayload\.memory_id/,
      /delete_status:\s*browserEvidence\.deleteStatus/,
      /detail_status_after_delete:\s*browserEvidence\.detailStatusAfterDelete/,
      /query:\s*httpEvidence\.query\.json/,
      /deleted:\s*\{\s*status_code:\s*browserEvidence\.deleteStatus\s*\}/s,
      /detail_after_delete:\s*\{\s*status_code:\s*browserEvidence\.detailStatusAfterDelete\s*\}/s,
    ],
  },
  'task-34': buildRemainingWebMemoryWriteValueCase({
    patterns: [
      /profile:\s*'memories_list'/,
      /archive_target_id:\s*httpEvidence\.archiveTargetId/,
      /delete_target_id:\s*httpEvidence\.deleteTargetId/,
      /archived_after_archive:\s*browserEvidence\.archivedAfterArchive\.json\?\.total/,
      /archive:\s*browserEvidence\.archivePayload/,
      /unarchive:\s*browserEvidence\.unarchivePayload/,
    ],
  }),
  'task-35': buildRemainingWebMemoryWriteValueCase({
    includeArchiveDetailPatterns: true,
    patterns: [
      /memory_id:\s*seedPayload\.memory_id/,
      /community_id:\s*seedPayload\.community_id/,
      /memory_detail_before:\s*httpEvidence\.memoryDetail\.json/,
      /memory_context_before:\s*httpEvidence\.memoryContext\.json/,
      /context_after_delete:\s*\{\s*status_code:\s*browserEvidence\.contextAfterDelete\.statusCode,\s*body:\s*browserEvidence\.contextAfterDelete\.json,\s*\}/s,
    ],
  }),
  'task-36': {
    patterns: [
      /query_modes_tested:\s*Object\.keys\(httpEvidence\.queryModes\)/,
      /global_query_source_memory_id:\s*httpEvidence\.queryModes\.global\.json\?\.sources\?\.\[0\]\?\.memory_id/,
      /local_query_source_memory_id:\s*httpEvidence\.queryModes\.local\.json\?\.sources\?\.\[0\]\?\.memory_id/,
      /hybrid_query_source_memory_id:\s*httpEvidence\.queryModes\.hybrid\.json\?\.sources\?\.\[0\]\?\.memory_id/,
      /link_surface:\s*'source'/,
      /memory_detail_requests:\s*browserEvidence\.memoryDetailRequestCount/,
      /memory_link_count:\s*browserEvidence\.memoryLinkCount/,
      /query_global:\s*httpEvidence\.queryModes\.global\.json/,
      /query_local:\s*httpEvidence\.queryModes\.local\.json/,
      /query_hybrid:\s*httpEvidence\.queryModes\.hybrid\.json/,
      /fake_ollama_counts:\s*httpEvidence\.fakeOllamaCounts/,
    ],
  },
  'task-37': buildRemainingWebMemoryDeleteFailureValueCase({
    includeAfterDeleteStatusPatterns: false,
    detailObjectPattern: /deleted_detail:\s*\{\s*status_code:\s*browserEvidence\.deletedDetail\.statusCode,\s*body:\s*browserEvidence\.deletedDetail\.json,\s*\}/s,
    contextObjectPattern: /deleted_context:\s*\{\s*status_code:\s*browserEvidence\.deletedContext\.statusCode,\s*body:\s*browserEvidence\.deletedContext\.json,\s*\}/s,
    patterns: [
      /seeded_memory_id:\s*seedPayload\.memory_id/,
      /missing_memory_id:\s*MISSING_MEMORY_ID/,
      /missing_detail_status:\s*httpEvidence\.missingDetail\.statusCode/,
      /missing_context_status:\s*httpEvidence\.missingContext\.statusCode/,
      /all_before_delete:\s*httpEvidence\.allBeforeDelete\.json/,
    ],
  }),
  'task-38': {
    patterns: [
      /existing_community_id:\s*httpEvidence\.existingCommunityId/,
      /missing_community_id:\s*MISSING_COMMUNITY_ID/,
      /missing_detail_status:\s*httpEvidence\.missingDetail\.statusCode/,
      /total_communities:\s*httpEvidence\.communities\.json\?\.total/,
      /communities:\s*httpEvidence\.communities\.json/,
      /missing_detail:\s*\{\s*status_code:\s*httpEvidence\.missingDetail\.statusCode,\s*body:\s*httpEvidence\.missingDetail\.json,\s*\}/s,
    ],
  },
  'task-40': buildRemainingWebCommunityFailureValueCase({
    tailPatterns: [
      /community_detail:\s*httpEvidence\.communityDetail\.json/,
      /ancestors:\s*\{\s*status_code:\s*httpEvidence\.ancestors\.statusCode,\s*body:\s*httpEvidence\.ancestors\.json,\s*\}/s,
      /descendants:\s*\{\s*status_code:\s*httpEvidence\.descendants\.statusCode,\s*body:\s*httpEvidence\.descendants\.json,\s*\}/s,
      /entities:\s*httpEvidence\.entities\.json/,
      /relationships:\s*httpEvidence\.relationships\.json/,
    ],
  }),
  'task-41': buildRemainingWebCommunityFailureValueCase({
    tailPatterns: [
      /community_detail:\s*httpEvidence\.communityDetail\.json/,
      /entities:\s*\{\s*status_code:\s*httpEvidence\.entities\.statusCode,\s*body:\s*httpEvidence\.entities\.json,\s*\}/s,
      /relationships:\s*\{\s*status_code:\s*httpEvidence\.relationships\.statusCode,\s*body:\s*httpEvidence\.relationships\.json,\s*\}/s,
      /ancestors:\s*httpEvidence\.ancestors\.json/,
      /descendants:\s*httpEvidence\.descendants\.json/,
    ],
  }),
  'task-43': buildRemainingWebCommunitySummaryRefreshValueCase(),
  'task-56': buildRemainingWebMemoryWriteValueCase({
    includeArchiveDetailPatterns: true,
    patterns: [
      /recent_memory_id:\s*seedPayload\.memory_id/,
      /navigation_surface:\s*'search_memory_link'/,
      /query_source_memory_id:\s*httpEvidence\.query\.json\?\.sources\?\.\[0\]\?\.memory_id/,
      /context_after_delete:\s*\{\s*status_code:\s*browserEvidence\.contextAfterDelete\.statusCode,\s*body:\s*browserEvidence\.contextAfterDelete\.json,\s*\}/s,
      /all_after_delete:\s*browserEvidence\.allAfterDelete\.json/,
    ],
  }),
  'task-57': buildRemainingWebMemoryDeleteFailureValueCase({
    patterns: [
      /recent_memory_id:\s*seedPayload\.memory_id/,
      /navigation_surface:\s*'search_memory_link'/,
      /query_source_memory_id:\s*httpEvidence\.query\.json\?\.sources\?\.\[0\]\?\.memory_id/,
    ],
  }),
})

export function assertFocusedRealSmokeRemainingWebValueContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeValueCase(taskId, qaScriptFile, source, REMAINING_WEB_VALUE_CASES_BY_TASK_ID, {
    missingCaseLabel: 'remaining-web value contract case',
    missingBindingLabel: 'expected remaining-web evidence binding',
  })
}
