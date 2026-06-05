import assert from 'node:assert/strict'

const QUERY_MODE_IDS = Object.freeze(['global', 'local', 'hybrid'])

function readPath(target, path) {
  return path.split('.').reduce((current, segment) => current?.[segment], target)
}

function buildQueryModeMap(mapper) {
  return Object.fromEntries(QUERY_MODE_IDS.map((modeId) => [modeId, mapper(modeId)]))
}

export function assertEvidenceFields(target, expected, label = 'evidence') {
  for (const [field, value] of Object.entries(expected)) {
    assert.deepEqual(target[field], value, `${label}.${field} mismatch`)
  }
}

export function assertEvidencePathValues(target, expected, label = 'evidence') {
  for (const [path, value] of Object.entries(expected)) {
    assert.deepEqual(readPath(target, path), value, `${label}.${path} mismatch`)
  }
}

export function buildFocusedRealSmokeEvidenceAssertion(taskId, {
  label = `${taskId} evidence`,
  fields,
  paths,
  customAssert,
} = {}) {
  return (target) => {
    if (fields) {
      assertEvidenceFields(target, fields, label)
    }
    if (paths) {
      assertEvidencePathValues(target, paths, label)
    }
    if (customAssert) {
      customAssert(target)
    }
  }
}

export function buildSettingsImportDiagnosticsEvidenceAssertion(taskId, {
  label = `${taskId} normalized`,
  healthProvider,
  fields,
  paths,
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields,
    paths,
    customAssert: (normalized) => {
      if (healthProvider !== undefined) {
        assert.equal(normalized.health.provider, healthProvider, `${label}.health.provider mismatch`)
      }
      if (customAssert) {
        customAssert(normalized)
      }
    },
  })
}

export function buildSuccessfulMemoryWriteLifecycleAssertion(taskId, {
  label = `${taskId} normalized`,
  finalRoute = '/memories',
  detailStatusAfterDelete = 404,
  contextStatusAfterDelete,
  includeArchiveOutcomeFields = false,
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(includeArchiveOutcomeFields ? {
        archive_success: true,
        unarchive_success: true,
      } : {}),
      delete_success: true,
      delete_message: 'Memory deleted',
      detail_status_after_delete: detailStatusAfterDelete,
      ...(contextStatusAfterDelete === undefined ? {} : { context_status_after_delete: contextStatusAfterDelete }),
      final_route: finalRoute,
      ...fieldAssertions,
    },
    paths: {
      'detail_after_delete.status_code': detailStatusAfterDelete,
      ...(contextStatusAfterDelete === undefined ? {} : { 'context_after_delete.status_code': contextStatusAfterDelete }),
      ...pathAssertions,
    },
    customAssert,
  })
}

export function buildNormalizedCommunityEvidenceAssertion(taskId, {
  label = `${taskId} normalized`,
  communityId,
  communityField = 'target_community_id',
  communityTitle,
  titleField = 'community_title',
  finalRoute = communityId ? `/communities#${communityId}` : undefined,
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(communityId === undefined ? {} : { [communityField]: communityId }),
      ...(communityTitle === undefined ? {} : { [titleField]: communityTitle }),
      ...(finalRoute === undefined ? {} : { final_route: finalRoute }),
      ...fieldAssertions,
    },
    paths: pathAssertions,
    customAssert,
  })
}

export function buildHighSignalCommunityDetailNavigationEvidenceAssertion(taskId, {
  label = `${taskId} evidence`,
  finalUrlCommunityField = 'community_id',
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return ({ summary, http }) => {
    assertEvidenceFields(summary, {
      memory_id: http.memory_detail.id,
      community_id: http.community_detail.id,
      memory_context_entities: http.memory_context.total_entities,
      memory_context_communities: http.memory_context.total_communities,
      community_entities_total: http.community_entities.total,
      community_relationships_total: http.community_relationships.total,
      ancestors_total: http.community_ancestors.total,
      descendants_total: http.community_descendants.total,
      ...fieldAssertions,
    }, `${label} summary`)

    assertEvidencePathValues(http, {
      'community_relationships.relationships.0.type': summary.community_relationship_type,
      ...pathAssertions,
    }, `${label} http`)

    if (finalUrlCommunityField) {
      assert.ok(
        summary.final_url.endsWith(`#${summary[finalUrlCommunityField]}`),
        `${label} summary.final_url mismatch`
      )
    }

    if (customAssert) {
      customAssert({ summary, http })
    }
  }
}

export function buildHighSignalSingleMemoryContextEvidenceAssertion(taskId, {
  label = `${taskId} evidence`,
  summaryMemoryIdField,
  memoryIdHttpPath,
  memoryIdMirrorSummaryFields = [],
  additionalMemoryIdHttpPaths = [],
  contextCountField,
  contextCountHttpPath = 'memory_context.total_communities',
  summaryCommunityIdField,
  communityIdHttpPath,
  communityIdMirrorSummaryFields = [],
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return ({ summary, http }) => {
    assertEvidenceFields(summary, {
      ...(summaryMemoryIdField && memoryIdHttpPath ? { [summaryMemoryIdField]: readPath(http, memoryIdHttpPath) } : {}),
      ...(contextCountField ? { [contextCountField]: readPath(http, contextCountHttpPath) } : {}),
      ...(summaryCommunityIdField && communityIdHttpPath ? { [summaryCommunityIdField]: readPath(http, communityIdHttpPath) } : {}),
      ...fieldAssertions,
    }, `${label} summary`)

    for (const field of memoryIdMirrorSummaryFields) {
      assert.deepEqual(summary[summaryMemoryIdField], summary[field], `${label} summary.${field} mismatch`)
    }

    for (const field of communityIdMirrorSummaryFields) {
      assert.deepEqual(summary[summaryCommunityIdField], summary[field], `${label} summary.${field} mismatch`)
    }

    assertEvidencePathValues(http, {
      ...Object.fromEntries(additionalMemoryIdHttpPaths.map((path) => [path, summary[summaryMemoryIdField]])),
      ...pathAssertions,
    }, `${label} http`)

    if (customAssert) {
      customAssert({ summary, http })
    }
  }
}

export function buildNormalizedCommunityDetailNavigationAssertion(taskId, {
  label = `${taskId} normalized`,
  communityId,
  communityTitle,
  communitySummary,
  memoryContextEntityNames = [],
  communityEntityNames = [],
  communityRelationships = [],
  ancestorTitles = [],
  descendantTitles = [],
  memoryContextCommunities = 0,
  communityEntitiesTotal = 0,
  communityRelationshipsTotal = 0,
  ancestorsTotal = 0,
  descendantsTotal = 0,
  finalRoute = communityId ? `/communities#${communityId}` : undefined,
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(communityId === undefined ? {} : { community_id: communityId }),
      memory_context_communities: memoryContextCommunities,
      community_entities_total: communityEntitiesTotal,
      community_relationships_total: communityRelationshipsTotal,
      ancestors_total: ancestorsTotal,
      descendants_total: descendantsTotal,
      community_id_matches_detail: true,
      ...(communityTitle === undefined ? {} : { community_title: communityTitle }),
      ...(communitySummary === undefined ? {} : { community_summary: communitySummary }),
      memory_context_entity_names: memoryContextEntityNames,
      community_entity_names: communityEntityNames,
      community_relationships: communityRelationships,
      ancestor_titles: ancestorTitles,
      descendant_titles: descendantTitles,
      ...(finalRoute === undefined ? {} : { final_route: finalRoute }),
      ...fieldAssertions,
    },
    paths: pathAssertions,
    customAssert,
  })
}

export function buildNormalizedCommunityMissingDetailAssertion(taskId, {
  label = `${taskId} normalized`,
  missingCommunityId,
  missingDetailStatus = 404,
  finalRoute = missingCommunityId ? `/communities#${missingCommunityId}` : undefined,
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(missingCommunityId === undefined ? {} : { missing_community_id: missingCommunityId }),
      missing_detail_status: missingDetailStatus,
      ...(finalRoute === undefined ? {} : { final_route: finalRoute }),
      ...fieldAssertions,
    },
    paths: {
      'missing_detail.status_code': missingDetailStatus,
      ...pathAssertions,
    },
    customAssert,
  })
}

export function buildDeletedMemoryFailureAssertion(taskId, {
  label = `${taskId} normalized`,
  finalRoute = '/memories',
  includeDeleteOutcomeFields = true,
  deleteStatusField,
  deleteStatus = 200,
  detailStatusField,
  detailStatus = 404,
  detailStatusPath,
  contextStatusField,
  contextStatus,
  contextStatusPath,
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  const resolvedDetailStatusPath = detailStatusPath
  const resolvedContextStatusPath = contextStatusPath

  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(includeDeleteOutcomeFields ? {
        delete_success: true,
        delete_message: 'Memory deleted',
      } : {}),
      ...(deleteStatusField === undefined ? {} : { [deleteStatusField]: deleteStatus }),
      ...(detailStatusField === undefined ? {} : { [detailStatusField]: detailStatus }),
      ...(contextStatusField === undefined ? {} : { [contextStatusField]: contextStatus }),
      final_route: finalRoute,
      ...fieldAssertions,
    },
    paths: {
      ...(resolvedDetailStatusPath === undefined ? {} : { [resolvedDetailStatusPath]: detailStatus }),
      ...(resolvedContextStatusPath === undefined ? {} : { [resolvedContextStatusPath]: contextStatus }),
      ...pathAssertions,
    },
    customAssert,
  })
}

export function buildDashboardGraphStatsEvidenceAssertion(taskId, {
  label = `${taskId} normalized`,
  navigationSurfaces,
  finalRoute = '/graph',
  includeTotalCommunities = false,
  includeRecentMemoriesTotal = true,
  includeCommunitiesTotal = true,
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(navigationSurfaces === undefined ? {} : { navigation_surfaces: navigationSurfaces }),
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      ...(includeTotalCommunities ? { total_communities: 0 } : {}),
      entity_types: {},
      ...(includeRecentMemoriesTotal ? { recent_memories_total: 0 } : {}),
      ...(includeCommunitiesTotal ? { communities_total: 0 } : {}),
      final_route: finalRoute,
      ...fieldAssertions,
    },
    paths: pathAssertions,
    customAssert,
  })
}

export function buildDashboardCommunitiesStatsEvidenceAssertion(taskId, {
  label = `${taskId} normalized`,
  navigationSurface,
  finalRoute = '/communities',
  includeTotalCommunities = false,
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(navigationSurface === undefined ? {} : { navigation_surface: navigationSurface }),
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      ...(includeTotalCommunities ? { total_communities: 0 } : {}),
      entity_types: {},
      recent_memories_total: 0,
      final_route: finalRoute,
      ...fieldAssertions,
    },
    paths: pathAssertions,
    customAssert,
  })
}

export function buildDashboardMemoriesStatsEvidenceAssertion(taskId, {
  label = `${taskId} normalized`,
  navigationSurface,
  finalRoute = '/memories',
  includeTotalMemories = true,
  includeEntityRelationshipTotals = false,
  includeTotalCommunities = false,
  includeEntityTypes = true,
  includeCommunitiesTotal = true,
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(navigationSurface === undefined ? {} : { navigation_surface: navigationSurface }),
      ...(includeEntityRelationshipTotals ? {
        total_entities: 0,
        total_relationships: 0,
      } : {}),
      ...(includeTotalMemories ? { total_memories: 0 } : {}),
      ...(includeTotalCommunities ? { total_communities: 0 } : {}),
      ...(includeEntityTypes ? { entity_types: {} } : {}),
      ...(includeCommunitiesTotal ? { communities_total: 0 } : {}),
      final_route: finalRoute,
      ...fieldAssertions,
    },
    paths: pathAssertions,
    customAssert,
  })
}

export function buildMissingMemoryIdCommunityFallbackAssertion(taskId, {
  label = `${taskId} normalized`,
  communityId,
  communityTitle,
  queryAnswer,
  queryAnswersByMode,
  linkSurface = 'source',
  queryModesTested = QUERY_MODE_IDS,
  querySourceMemoryIdsByMode = buildQueryModeMap(() => null),
  memoryDetailRequests = 0,
  memoryLinkCount = 0,
  memoriesTotal = 0,
  communitiesTotal = 1,
  queryCommunityIdsByMode = buildQueryModeMap(() => [communityId]),
  fakeOllamaCounts,
  finalRoute = communityId ? `/communities#${communityId}` : undefined,
  fieldAssertions = {},
  customAssert,
} = {}) {
  const expectedQueryAnswers = queryAnswersByMode ?? buildQueryModeMap(() => queryAnswer)

  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(communityId === undefined ? {} : { community_id: communityId }),
      query_modes_tested: queryModesTested,
      global_query_source_memory_id: querySourceMemoryIdsByMode.global,
      local_query_source_memory_id: querySourceMemoryIdsByMode.local,
      hybrid_query_source_memory_id: querySourceMemoryIdsByMode.hybrid,
      link_surface: linkSurface,
      memory_detail_requests: memoryDetailRequests,
      memory_link_count: memoryLinkCount,
      memories_total: memoriesTotal,
      communities_total: communitiesTotal,
      ...(communityTitle === undefined ? {} : { community_title: communityTitle }),
      ...(fakeOllamaCounts === undefined ? {} : { fake_ollama_counts: fakeOllamaCounts }),
      ...(finalRoute === undefined ? {} : { final_route: finalRoute }),
      ...fieldAssertions,
    },
    customAssert: (normalized) => {
      assert.deepEqual(normalized.query_answers, expectedQueryAnswers, `${label}.query_answers mismatch`)
      assert.deepEqual(normalized.query_community_ids, queryCommunityIdsByMode, `${label}.query_community_ids mismatch`)
      if (customAssert) {
        customAssert(normalized)
      }
    },
  })
}

export function buildHighSignalCommunityMissingDetailEvidenceAssertion(taskId, {
  label = `${taskId} evidence`,
  linkSurface,
  matchingSummaryFields = [],
} = {}) {
  return ({ summary, http }) => {
    assertEvidenceFields(summary, {
      link_surface: linkSurface,
      missing_detail_status: 404,
    }, `${label} summary`)

    for (const field of matchingSummaryFields) {
      assert.deepEqual(summary.community_id, summary[field], `${label} summary.${field} mismatch`)
    }

    assertEvidencePathValues(http, {
      'missing_detail.status_code': 404,
    }, `${label} http`)
    assert.ok(summary.final_url.endsWith(`#${summary.missing_community_id}`))
  }
}

export function buildHighSignalCommunityDataFailureEvidenceAssertion(taskId, {
  label = `${taskId} evidence`,
  linkSurface,
  targetCommunityField = 'target_community_id',
  matchingSummaryField,
  includeQueryCommunityMembership = false,
  includeCommunityTitle = false,
} = {}) {
  return ({ summary, http }) => {
    assertEvidenceFields(summary, {
      link_surface: linkSurface,
      ...(includeCommunityTitle ? { community_title: http.community_detail.title } : {}),
      entities_status: 500,
      relationships_status: 500,
      ancestors_status: 200,
      descendants_status: 200,
    }, `${label} summary`)

    if (matchingSummaryField) {
      assert.deepEqual(
        summary[targetCommunityField],
        summary[matchingSummaryField],
        `${label} summary.${matchingSummaryField} mismatch`
      )
    }

    if (includeQueryCommunityMembership) {
      assert.ok(summary.query_community_ids.includes(summary[targetCommunityField]))
    }

    assertEvidencePathValues(http, {
      'entities.status_code': summary.entities_status,
      'relationships.status_code': summary.relationships_status,
      'ancestors.community_id': summary[targetCommunityField],
      'descendants.community_id': summary[targetCommunityField],
    }, `${label} http`)
    assert.ok(summary.final_url.endsWith(`#${summary[targetCommunityField]}`))
  }
}

export function buildHighSignalCommunitySummaryRefreshEvidenceAssertion(taskId, {
  label = `${taskId} evidence`,
  linkSurface,
  beforeSummaryField = 'before_summary',
  communityIdField,
  communityIdHttpPath,
  matchingSummaryField,
  includeQueryCommunityMembership = false,
  includeEntityRelationshipStatuses = false,
  refreshedSummaryMirrorHttpPath,
  finalUrlCommunityField,
} = {}) {
  return ({ summary, http }) => {
    assertEvidenceFields(summary, {
      ...(linkSurface === undefined ? {} : { link_surface: linkSurface }),
      [beforeSummaryField]: http.before_summary.summary,
      refreshed_summary: http.after_summary.summary,
      ...(includeEntityRelationshipStatuses ? {
        entities_status: http.entities.status_code,
        relationships_status: http.relationships.status_code,
      } : {}),
    }, `${label} summary`)

    if (matchingSummaryField) {
      assert.deepEqual(
        summary.target_community_id,
        summary[matchingSummaryField],
        `${label} summary.${matchingSummaryField} mismatch`
      )
    }

    if (communityIdField && communityIdHttpPath) {
      assert.deepEqual(
        summary[communityIdField],
        readPath(http, communityIdHttpPath),
        `${label} summary.${communityIdField} mismatch`
      )
    }

    if (includeQueryCommunityMembership) {
      assert.ok(summary.query_community_ids.includes(summary.target_community_id))
    }

    if (refreshedSummaryMirrorHttpPath) {
      assert.deepEqual(
        summary.refreshed_summary,
        readPath(http, refreshedSummaryMirrorHttpPath),
        `${label} summary.refreshed_summary mirror mismatch`
      )
    }

    assert.notDeepEqual(summary[beforeSummaryField], summary.refreshed_summary, `${label} summary refresh should change output`)

    if (finalUrlCommunityField) {
      assert.ok(
        summary.final_url.endsWith(`/communities#${summary[finalUrlCommunityField]}`),
        `${label} summary.final_url mismatch`
      )
    }
  }
}

export function buildNormalizedCommunitySummaryRefreshAssertion(taskId, {
  label = `${taskId} normalized`,
  communityId,
  initialSummaryField = 'before_summary',
  initialSummaryValue,
  refreshedSummaryValue,
  matchRefreshedFields = [],
  fieldAssertions = {},
  pathAssertions = {},
  customAssert,
} = {}) {
  return buildFocusedRealSmokeEvidenceAssertion(taskId, {
    label,
    fields: {
      ...(communityId === undefined ? {} : { community_id: communityId }),
      [initialSummaryField]: initialSummaryValue,
      refreshed_summary: refreshedSummaryValue,
      summary_changed: true,
      ...(communityId === undefined ? {} : { final_route: `/communities#${communityId}` }),
      ...fieldAssertions,
    },
    paths: pathAssertions,
    customAssert: (normalized) => {
      assert.notDeepEqual(
        normalized[initialSummaryField],
        normalized.refreshed_summary,
        `${label} ${initialSummaryField} should differ from refreshed_summary`
      )

      for (const field of matchRefreshedFields) {
        assert.deepEqual(normalized[field], normalized.refreshed_summary, `${label}.${field} mismatch`)
      }

      if (customAssert) {
        customAssert(normalized)
      }
    },
  })
}
