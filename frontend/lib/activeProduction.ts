/**
 * Client-side mirror of the active production id.
 * Authoritative source: GET/PUT /api/v1/productions/active
 * (see docs/active-production.md).
 */
const STORAGE_KEY = "tm.activeProductionId";

export function getMirroredActiveProductionId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setMirroredActiveProductionId(productionId: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (productionId) localStorage.setItem(STORAGE_KEY, productionId);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore quota / private mode */
  }
}
