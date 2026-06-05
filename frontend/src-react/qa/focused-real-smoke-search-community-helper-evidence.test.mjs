import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildHighSignalCommunityDataFailureEvidenceAssertion,
  buildHighSignalCommunityMissingDetailEvidenceAssertion,
  buildHighSignalCommunitySummaryRefreshEvidenceAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'

test('buildHighSignalCommunityMissingDetailEvidenceAssertion applies stale-link defaults', () => {
  const assertion = buildHighSignalCommunityMissingDetailEvidenceAssertion('task-community-stale', {
    linkSurface: 'source',
    matchingSummaryFields: ['query_source_community_id', 'query_hit_community_id'],
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        community_id: 'comm-launch-owners',
        query_source_community_id: 'comm-launch-owners',
        query_hit_community_id: 'comm-launch-owners',
        missing_community_id: 'comm-missing',
        link_surface: 'source',
        missing_detail_status: 404,
        final_url: '/search#comm-missing',
      },
      http: {
        missing_detail: { status_code: 404 },
      },
    })
  })
})

test('buildHighSignalCommunityDataFailureEvidenceAssertion applies status and target-community defaults', () => {
  const assertion = buildHighSignalCommunityDataFailureEvidenceAssertion('task-community-data', {
    linkSurface: 'source',
    matchingSummaryField: 'query_source_community_id',
    includeCommunityTitle: true,
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        target_community_id: 'comm-release-readiness',
        query_source_community_id: 'comm-release-readiness',
        link_surface: 'source',
        community_title: 'Release Readiness',
        entities_status: 500,
        relationships_status: 500,
        ancestors_status: 200,
        descendants_status: 200,
        final_url: '/communities#comm-release-readiness',
      },
      http: {
        community_detail: { title: 'Release Readiness' },
        entities: { status_code: 500 },
        relationships: { status_code: 500 },
        ancestors: { community_id: 'comm-release-readiness' },
        descendants: { community_id: 'comm-release-readiness' },
      },
    })
  })
})

test('buildHighSignalCommunityDataFailureEvidenceAssertion supports query community membership checks', () => {
  const assertion = buildHighSignalCommunityDataFailureEvidenceAssertion('task-community-data-result', {
    linkSurface: 'result',
    includeQueryCommunityMembership: true,
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        target_community_id: 'comm-release-readiness',
        query_community_ids: ['comm-release-readiness'],
        link_surface: 'result',
        entities_status: 500,
        relationships_status: 500,
        ancestors_status: 200,
        descendants_status: 200,
        final_url: '/communities#comm-release-readiness',
      },
      http: {
        entities: { status_code: 500 },
        relationships: { status_code: 500 },
        ancestors: { community_id: 'comm-release-readiness' },
        descendants: { community_id: 'comm-release-readiness' },
      },
    })
  })
})

test('buildHighSignalCommunitySummaryRefreshEvidenceAssertion applies refresh defaults and optional status checks', () => {
  const assertion = buildHighSignalCommunitySummaryRefreshEvidenceAssertion('task-community-refresh', {
    linkSurface: 'result',
    includeQueryCommunityMembership: true,
    includeEntityRelationshipStatuses: true,
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        link_surface: 'result',
        before_summary: 'stale summary',
        refreshed_summary: 'fresh summary',
        target_community_id: 'comm-release-readiness',
        query_community_ids: ['comm-release-readiness'],
        entities_status: 500,
        relationships_status: 500,
      },
      http: {
        before_summary: { summary: 'stale summary' },
        after_summary: { summary: 'fresh summary' },
        entities: { status_code: 500 },
        relationships: { status_code: 500 },
      },
    })
  })
})

test('buildHighSignalCommunitySummaryRefreshEvidenceAssertion supports custom before-summary fields', () => {
  const assertion = buildHighSignalCommunitySummaryRefreshEvidenceAssertion('task-community-refresh-initial', {
    beforeSummaryField: 'initial_summary',
    communityIdField: 'community_id',
    communityIdHttpPath: 'before_summary.id',
    refreshedSummaryMirrorHttpPath: 'regenerate.summary',
    finalUrlCommunityField: 'community_id',
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        community_id: 'comm-launch-owners',
        initial_summary: 'stale summary',
        refreshed_summary: 'fresh summary',
        final_url: '/communities#comm-launch-owners',
      },
      http: {
        before_summary: { id: 'comm-launch-owners', summary: 'stale summary' },
        after_summary: { summary: 'fresh summary' },
        regenerate: { summary: 'fresh summary' },
      },
    })
  })
})

test('buildHighSignalCommunitySummaryRefreshEvidenceAssertion supports community id and final url checks', () => {
  const assertion = buildHighSignalCommunitySummaryRefreshEvidenceAssertion('task-community-refresh-id', {
    communityIdField: 'community_id',
    communityIdHttpPath: 'before_summary.id',
    refreshedSummaryMirrorHttpPath: 'regenerate.summary',
    finalUrlCommunityField: 'community_id',
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        community_id: 'comm-launch-owners',
        before_summary: 'stale summary',
        refreshed_summary: 'fresh summary',
        final_url: '/communities#comm-launch-owners',
      },
      http: {
        before_summary: { id: 'comm-launch-owners', summary: 'stale summary' },
        after_summary: { summary: 'fresh summary' },
        regenerate: { summary: 'fresh summary' },
      },
    })
  })
})
