import {
  buildSearchCommunityDataFailureNormalizer,
  buildSearchCommunityMissingDetailNormalizer,
  buildSearchCommunitySummaryRefreshNormalizer,
  createTaskCase,
} from './helpers.mjs'

export const SEARCH_COMMUNITY_ADJACENT_TASK_CASES = {
  'task-39': createTaskCase('task-39', {
    normalize: buildSearchCommunityMissingDetailNormalizer({
      includeQuerySourceMatch: true,
      includeQueryHitMatch: true,
      includeQueryAnswer: true,
      includeQueryCommunityIds: true,
    }),
  }),
  'task-42': createTaskCase('task-42', {
    normalize: buildSearchCommunityDataFailureNormalizer({
      includeQueryCommunityIds: true,
      includeQuerySourceCommunityIds: true,
      includeAncestorTitles: true,
      includeDescendantTitles: true,
    }),
  }),
  'task-44': createTaskCase('task-44', {
    normalize: buildSearchCommunitySummaryRefreshNormalizer({
      includeQueryCommunityIds: true,
      includeAncestorTitles: true,
    }),
  }),
  'task-58': createTaskCase('task-58', {
    normalize: buildSearchCommunitySummaryRefreshNormalizer({
      includeQuerySourceMatch: true,
    }),
  }),
  'task-59': createTaskCase('task-59', {
    normalize: buildSearchCommunityMissingDetailNormalizer({
      includeQueryHitMatch: true,
    }),
  }),
  'task-60': createTaskCase('task-60', {
    normalize: buildSearchCommunityDataFailureNormalizer({
      includeQuerySourceMatch: true,
      includeCommunityTitle: true,
      includeDetailTitle: true,
      includeAncestorTitles: true,
    }),
  }),
}
