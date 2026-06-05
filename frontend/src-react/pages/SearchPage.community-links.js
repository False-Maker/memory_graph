function normalizeCommunityId(value) {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  return text ? text : null
}

export function buildCommunitiesHashHref(communityId) {
  const normalized = normalizeCommunityId(communityId)
  if (!normalized) return null
  return `/communities#${encodeURIComponent(normalized)}`
}

