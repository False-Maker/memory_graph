function normalizeCommunityId(value) {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  return text || null
}

export function buildCommunitiesHashHref(communityId) {
  const normalized = normalizeCommunityId(communityId)
  if (!normalized) return null
  return `/communities#${encodeURIComponent(normalized)}`
}

export function buildInitialMemoryContext() {
  return {
    entities: [],
    communities: [],
  }
}

export function normalizeMemoryContextPayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return buildInitialMemoryContext()
  }

  return {
    entities: Array.isArray(payload.entities) ? payload.entities : [],
    communities: Array.isArray(payload.communities) ? payload.communities : [],
  }
}

export function hasMemoryContextContent(context) {
  return (
    Array.isArray(context?.entities) && context.entities.length > 0
  ) || (
    Array.isArray(context?.communities) && context.communities.length > 0
  )
}
