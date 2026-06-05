const DETAIL_KEYS = ['entities', 'relationships', 'ancestors', 'descendants']

export function normalizeCommunityIdFromHash(hash) {
  const raw = String(hash || '').replace(/^#/, '').trim()
  if (!raw) return null
  try {
    const decoded = decodeURIComponent(raw).trim()
    return decoded || null
  } catch {
    return raw
  }
}

export function buildCommunityHash(communityId) {
  const normalized = String(communityId || '').trim()
  return normalized ? `#${encodeURIComponent(normalized)}` : ''
}

export function buildInitialFacetData() {
  return {
    entities: [],
    relationships: [],
    ancestors: [],
    descendants: [],
  }
}

export function buildInitialFacetLoading() {
  return {
    entities: false,
    relationships: false,
    ancestors: false,
    descendants: false,
  }
}

export function buildInitialFacetErrors() {
  return {
    entities: null,
    relationships: null,
    ancestors: null,
    descendants: null,
  }
}

export function normalizeFacetPayload(key, payload) {
  if (Array.isArray(payload)) return payload
  if (!payload || typeof payload !== 'object') return []
  if (Array.isArray(payload[key])) return payload[key]
  return []
}

export function hasAnyFacetContent(facetData) {
  return DETAIL_KEYS.some((key) => Array.isArray(facetData?.[key]) && facetData[key].length > 0)
}

