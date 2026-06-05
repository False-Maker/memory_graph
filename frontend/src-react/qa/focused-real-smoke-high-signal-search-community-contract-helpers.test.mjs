import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildHighSignalCommunityDataFailureSchemaCase,
  buildHighSignalCommunityDataFailureValueCase,
  buildHighSignalCommunityMissingDetailSchemaCase,
  buildHighSignalCommunityMissingDetailValueCase,
  buildHighSignalCommunitySummaryRefreshSchemaCase,
  buildHighSignalCommunitySummaryRefreshValueCase,
} from './focused-real-smoke-high-signal-search-community-contract-helpers.mjs'

test('buildHighSignalCommunityMissingDetailSchemaCase supports source and result variants', () => {
  assert.deepEqual(
    buildHighSignalCommunityMissingDetailSchemaCase({
      includeQuerySourceCommunityId: true,
      includeQueryHitCommunityId: true,
    }),
    {
      summaryKeys: [
        'community_id',
        'missing_community_id',
        'link_surface',
        'query_source_community_id',
        'query_hit_community_id',
        'missing_detail_status',
      ],
      httpKeys: ['health', 'query', 'community_detail', 'missing_detail'],
    }
  )

  assert.deepEqual(
    buildHighSignalCommunityMissingDetailSchemaCase({
      includeQueryHitCommunityId: true,
    }),
    {
      summaryKeys: [
        'community_id',
        'missing_community_id',
        'link_surface',
        'query_hit_community_id',
        'missing_detail_status',
      ],
      httpKeys: ['health', 'query', 'community_detail', 'missing_detail'],
    }
  )
})

test('buildHighSignalCommunityDataFailureSchemaCase supports result and source variants', () => {
  assert.deepEqual(
    buildHighSignalCommunityDataFailureSchemaCase({
      includeQueryCommunityIds: true,
    }),
    {
      summaryKeys: [
        'target_community_id',
        'query_community_ids',
        'link_surface',
        'entities_status',
        'relationships_status',
        'ancestors_status',
        'descendants_status',
      ],
      httpKeys: ['health', 'query', 'entities', 'relationships', 'ancestors', 'descendants'],
    }
  )

  assert.deepEqual(
    buildHighSignalCommunityDataFailureSchemaCase({
      includeQuerySourceCommunityId: true,
      includeCommunityTitle: true,
    }),
    {
      summaryKeys: [
        'target_community_id',
        'query_source_community_id',
        'link_surface',
        'community_title',
        'entities_status',
        'relationships_status',
        'ancestors_status',
        'descendants_status',
      ],
      httpKeys: ['health', 'query', 'community_detail', 'entities', 'relationships', 'ancestors', 'descendants'],
    }
  )
})

test('buildHighSignalCommunitySummaryRefreshSchemaCase supports result and source variants', () => {
  assert.deepEqual(
    buildHighSignalCommunitySummaryRefreshSchemaCase({
      includeQueryCommunityIds: true,
    }),
    {
      summaryKeys: [
        'target_community_id',
        'query_community_ids',
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
  )

  assert.deepEqual(
    buildHighSignalCommunitySummaryRefreshSchemaCase({
      includeQuerySourceCommunityId: true,
    }),
    {
      summaryKeys: [
        'target_community_id',
        'query_source_community_id',
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
  )
})

test('buildHighSignalCommunityMissingDetailValueCase supports source and result variants', () => {
  const sourceCase = buildHighSignalCommunityMissingDetailValueCase({
    linkSurface: 'source',
    includeQuerySourceCommunityId: true,
    includeQueryHitCommunityId: true,
  })

  assert.equal(sourceCase.patterns.length, 5)
  assert.match("link_surface: 'source'", sourceCase.patterns[0])
  assert.match('query_source_community_id: httpEvidence.query.json?.sources?.[0]?.community_id', sourceCase.patterns[1])
  assert.match('query_hit_community_id: httpEvidence.query.json?.communities?.[0]?.community_id', sourceCase.patterns[2])

  const resultCase = buildHighSignalCommunityMissingDetailValueCase({
    linkSurface: 'result',
    includeQueryHitCommunityId: true,
  })

  assert.equal(resultCase.patterns.length, 4)
  assert.match("link_surface: 'result'", resultCase.patterns[0])
  assert.match('query_hit_community_id: httpEvidence.query.json?.communities?.[0]?.community_id', resultCase.patterns[1])
})

test('buildHighSignalCommunityDataFailureValueCase supports result and source variants', () => {
  const resultCase = buildHighSignalCommunityDataFailureValueCase({
    linkSurface: 'result',
    includeQueryCommunityIds: true,
    includeAncestorDescendantStatusPatterns: true,
    includeRelationshipsPattern: true,
  })

  assert.match("link_surface: 'result'", resultCase.patterns[0])
  assert.ok(resultCase.patterns.some((pattern) => pattern.test('query_community_ids: (httpEvidence.query.json?.communities || []).map((community) => community.community_id)')))
  assert.ok(resultCase.patterns.some((pattern) => pattern.test('ancestors_status: httpEvidence.ancestors.statusCode')))
  assert.ok(resultCase.patterns.some((pattern) => pattern.test('relationships: { status_code: httpEvidence.relationships.statusCode, body: httpEvidence.relationships.json, }')))

  const sourceCase = buildHighSignalCommunityDataFailureValueCase({
    linkSurface: 'source',
    includeQuerySourceCommunityId: true,
    includeCommunityTitle: true,
    includeCommunityDetailPattern: true,
  })

  assert.match("link_surface: 'source'", sourceCase.patterns[0])
  assert.ok(sourceCase.patterns.some((pattern) => pattern.test('query_source_community_id: httpEvidence.query.json?.sources?.[0]?.community_id')))
  assert.ok(sourceCase.patterns.some((pattern) => pattern.test('community_title: httpEvidence.communityDetail.json?.title')))
  assert.ok(sourceCase.patterns.some((pattern) => pattern.test('community_detail: httpEvidence.communityDetail.json')))
})

test('buildHighSignalCommunitySummaryRefreshValueCase supports result and source variants', () => {
  const resultCase = buildHighSignalCommunitySummaryRefreshValueCase({
    linkSurface: 'result',
    includeQueryCommunityIds: true,
    includeEntityRelationshipStatusPatterns: true,
  })

  assert.match("link_surface: 'result'", resultCase.patterns[0])
  assert.ok(resultCase.patterns.some((pattern) => pattern.test('query_community_ids: (httpEvidence.query.json?.communities || []).map((community) => community.community_id)')))
  assert.ok(resultCase.patterns.some((pattern) => pattern.test('entities_status: httpEvidence.entities.statusCode')))

  const sourceCase = buildHighSignalCommunitySummaryRefreshValueCase({
    linkSurface: 'source',
    includeQuerySourceCommunityId: true,
  })

  assert.match("link_surface: 'source'", sourceCase.patterns[0])
  assert.ok(sourceCase.patterns.some((pattern) => pattern.test('query_source_community_id: httpEvidence.query.json?.sources?.[0]?.community_id')))
  assert.ok(sourceCase.patterns.some((pattern) => pattern.test('after_summary: afterSummary.json')))
})
