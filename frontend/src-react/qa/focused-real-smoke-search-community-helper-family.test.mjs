import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildSearchCommunityDataFailureNormalizer,
  buildSearchCommunityMissingDetailNormalizer,
  buildSearchCommunitySummaryRefreshNormalizer,
} from './focused-real-smoke-compare-cases/helpers.mjs'

test('buildSearchCommunityMissingDetailNormalizer keeps missing-detail payload and requested match flags', () => {
  const normalize = buildSearchCommunityMissingDetailNormalizer({
    includeQuerySourceMatch: true,
    includeQueryHitMatch: true,
    includeQueryAnswer: true,
    includeQueryCommunityIds: true,
  })

  const result = normalize({
    summary: {
      command: 'node task-39',
      status: 'passed',
      community_id: 'comm-launch-owners',
      missing_community_id: 'comm-missing',
      link_surface: 'source',
      missing_detail_status: 404,
      final_url: 'http://127.0.0.1:4173/communities#comm-missing',
      query_source_community_id: 'comm-launch-owners',
      query_hit_community_id: 'comm-launch-owners',
    },
    http: {
      health: { status: 'healthy' },
      query: {
        answer: 'Alice owns the launch checklist.',
        communities: [{ community_id: 'comm-launch-owners', title: 'Launch Owners' }],
      },
      community_detail: { title: 'Launch Owners' },
      missing_detail: { status_code: 404, body: { detail: 'not found' } },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-39',
    status: 'passed',
    community_id: 'comm-launch-owners',
    missing_community_id: 'comm-missing',
    link_surface: 'source',
    missing_detail_status: 404,
    final_route: '/communities#comm-missing',
    query_source_matches_community: true,
    query_hit_matches_community: true,
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    query_answer: 'Alice owns the launch checklist.',
    query_community_ids: ['comm-launch-owners'],
    query_titles: ['Launch Owners'],
    community_title: 'Launch Owners',
    missing_detail: {
      status_code: 404,
      detail: 'not found',
    },
  })
})

test('buildSearchCommunityDataFailureNormalizer supports result-linked aggregate variants', () => {
  const normalize = buildSearchCommunityDataFailureNormalizer({
    includeQueryCommunityIds: true,
    includeQuerySourceCommunityIds: true,
    includeAncestorTitles: true,
    includeDescendantTitles: true,
  })

  const result = normalize({
    summary: {
      command: 'node task-42',
      status: 'passed',
      target_community_id: 'comm-release-readiness',
      query_community_ids: ['comm-release-readiness'],
      link_surface: 'result',
      entities_status: 500,
      relationships_status: 500,
      ancestors_status: 200,
      descendants_status: 200,
      final_url: 'http://127.0.0.1:4173/communities#comm-release-readiness',
    },
    http: {
      health: { status: 'healthy' },
      query: {
        communities: [{ title: 'Release Readiness' }],
        sources: [{ community_id: 'comm-release-readiness' }],
      },
      entities: { body: { detail: 'entities failed' } },
      relationships: { body: { detail: 'relationships failed' } },
      ancestors: { ancestors: [{ title: 'Level 2 Cluster 1' }], total: 1 },
      descendants: { descendants: [{ title: 'Launch Owners' }], total: 1 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-42',
    status: 'passed',
    target_community_id: 'comm-release-readiness',
    query_community_ids: ['comm-release-readiness'],
    link_surface: 'result',
    entities_status: 500,
    relationships_status: 500,
    ancestors_status: 200,
    descendants_status: 200,
    final_route: '/communities#comm-release-readiness',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    query_titles: ['Release Readiness'],
    query_source_community_ids: ['comm-release-readiness'],
    entities_error_detail: 'entities failed',
    relationships_error_detail: 'relationships failed',
    ancestor_titles: ['Level 2 Cluster 1'],
    ancestor_total: 1,
    descendant_titles: ['Launch Owners'],
    descendant_total: 1,
  })
})

test('buildSearchCommunityDataFailureNormalizer supports source-linked title and match variants', () => {
  const normalize = buildSearchCommunityDataFailureNormalizer({
    includeQuerySourceMatch: true,
    includeCommunityTitle: true,
    includeDetailTitle: true,
    includeAncestorTitles: true,
  })

  const result = normalize({
    summary: {
      command: 'node task-60',
      status: 'passed',
      target_community_id: 'comm-launch-owners',
      link_surface: 'source',
      community_title: 'Launch Owners',
      entities_status: 500,
      relationships_status: 500,
      ancestors_status: 200,
      descendants_status: 200,
      final_url: '/communities#comm-launch-owners',
      query_source_community_id: 'comm-launch-owners',
    },
    http: {
      health: { status: 'healthy' },
      query: { communities: [{ title: 'Launch Owners' }] },
      community_detail: { title: 'Launch Owners' },
      entities: { body: { detail: 'entities failed' } },
      relationships: { body: { detail: 'relationships failed' } },
      ancestors: { ancestors: [{ title: 'Level 2 Cluster 1' }], total: 1 },
      descendants: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-60',
    status: 'passed',
    target_community_id: 'comm-launch-owners',
    link_surface: 'source',
    community_title: 'Launch Owners',
    entities_status: 500,
    relationships_status: 500,
    ancestors_status: 200,
    descendants_status: 200,
    final_route: '/communities#comm-launch-owners',
    query_source_matches_target: true,
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    query_titles: ['Launch Owners'],
    detail_title: 'Launch Owners',
    entities_error_detail: 'entities failed',
    relationships_error_detail: 'relationships failed',
    ancestor_titles: ['Level 2 Cluster 1'],
    ancestor_total: 1,
    descendant_total: 0,
  })
})

test('buildSearchCommunitySummaryRefreshNormalizer supports result-linked summary refresh variants', () => {
  const normalize = buildSearchCommunitySummaryRefreshNormalizer({
    includeQueryCommunityIds: true,
    includeAncestorTitles: true,
  })

  const result = normalize({
    summary: {
      command: 'node task-44',
      status: 'passed',
      target_community_id: 'comm-release-readiness',
      query_community_ids: ['comm-release-readiness'],
      link_surface: 'result',
      before_summary: 'stale summary',
      refreshed_summary: 'fresh summary',
      entities_status: 500,
      relationships_status: 500,
      ancestors_status: 200,
      descendants_status: 200,
      final_url: '/communities#comm-release-readiness',
    },
    http: {
      health: { status: 'healthy' },
      query: { communities: [{ title: 'Release Readiness' }] },
      before_summary: { title: 'Release Readiness' },
      after_summary: { title: 'Release Readiness' },
      entities: { body: { detail: 'entities failed' } },
      relationships: { body: { detail: 'relationships failed' } },
      ancestors: { ancestors: [{ title: 'Level 2 Cluster 1' }], total: 1 },
      descendants: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-44',
    status: 'passed',
    target_community_id: 'comm-release-readiness',
    query_community_ids: ['comm-release-readiness'],
    link_surface: 'result',
    before_summary: 'stale summary',
    refreshed_summary: 'fresh summary',
    summary_changed: true,
    entities_status: 500,
    relationships_status: 500,
    ancestors_status: 200,
    descendants_status: 200,
    final_route: '/communities#comm-release-readiness',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    query_titles: ['Release Readiness'],
    before_title: 'Release Readiness',
    after_title: 'Release Readiness',
    entities_error_detail: 'entities failed',
    relationships_error_detail: 'relationships failed',
    ancestor_titles: ['Level 2 Cluster 1'],
    ancestor_total: 1,
    descendant_total: 0,
  })
})

test('buildSearchCommunitySummaryRefreshNormalizer supports source-linked target match variants', () => {
  const normalize = buildSearchCommunitySummaryRefreshNormalizer({
    includeQuerySourceMatch: true,
  })

  const result = normalize({
    summary: {
      command: 'node task-58',
      status: 'passed',
      target_community_id: 'comm-launch-owners',
      link_surface: 'source',
      before_summary: 'stale summary',
      refreshed_summary: 'fresh summary',
      entities_status: 500,
      relationships_status: 500,
      ancestors_status: 200,
      descendants_status: 200,
      final_url: '/communities#comm-launch-owners',
      query_source_community_id: 'comm-launch-owners',
    },
    http: {
      health: { status: 'healthy' },
      query: { communities: [{ title: 'Launch Owners' }] },
      before_summary: { title: 'Launch Owners' },
      after_summary: { title: 'Launch Owners' },
      entities: { body: { detail: 'entities failed' } },
      relationships: { body: { detail: 'relationships failed' } },
      ancestors: { total: 1 },
      descendants: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-58',
    status: 'passed',
    target_community_id: 'comm-launch-owners',
    link_surface: 'source',
    before_summary: 'stale summary',
    refreshed_summary: 'fresh summary',
    summary_changed: true,
    entities_status: 500,
    relationships_status: 500,
    ancestors_status: 200,
    descendants_status: 200,
    final_route: '/communities#comm-launch-owners',
    query_source_matches_target: true,
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    query_titles: ['Launch Owners'],
    before_title: 'Launch Owners',
    after_title: 'Launch Owners',
    entities_error_detail: 'entities failed',
    relationships_error_detail: 'relationships failed',
    ancestor_total: 1,
    descendant_total: 0,
  })
})
