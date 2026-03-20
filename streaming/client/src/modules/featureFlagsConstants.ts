/** Client-side freshness for GET /v1/auth/feature-flags/ (team map). Server still caches 24h. */
export const MAX_FRONTEND_FF_TTL_MS = 30 * 60 * 1000;

export function isFeatureFlagsClientCacheStale(checkedAt: number | null): boolean {
  if (checkedAt == null) return true;
  return Date.now() - checkedAt > MAX_FRONTEND_FF_TTL_MS;
}
