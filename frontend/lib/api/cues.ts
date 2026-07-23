import { apiFetch, apiFetchJson } from "@/lib/api/base";
import type {
  Cue,
  CueCreateInput,
  CueExecutionResult,
  CueUpdateInput,
  LegacyCueSummary
} from "@/lib/types/cue";
import type { CueType } from "@/lib/types/cue";

export type ListCuesParams = {
  productionId?: string;
  cueType?: CueType;
  enabled?: boolean;
};

function detailFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export async function listCues(params: ListCuesParams = {}): Promise<Cue[]> {
  const query = new URLSearchParams();
  if (params.productionId) query.set("production_id", params.productionId);
  if (params.cueType) query.set("cue_type", params.cueType);
  if (params.enabled != null) query.set("enabled", String(params.enabled));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetchJson<Cue[]>(`/cues${suffix}`);
}

export async function fetchCue(id: string, productionId?: string): Promise<Cue> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  return apiFetchJson<Cue>(`/cues/${id}${query}`);
}

export async function createCue(input: CueCreateInput): Promise<Cue> {
  return apiFetchJson<Cue>("/cues", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function updateCue(id: string, input: CueUpdateInput): Promise<Cue> {
  return apiFetchJson<Cue>(`/cues/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function deleteCue(id: string, productionId?: string): Promise<void> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  const res = await apiFetch(`/cues/${id}${query}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Löschen fehlgeschlagen" }));
    throw new Error(detailFromBody(err, "Löschen fehlgeschlagen"));
  }
}

/** Always dry-run — UI never requests real hardware send. */
export async function dryRunCue(id: string, productionId?: string): Promise<CueExecutionResult> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  return apiFetchJson<CueExecutionResult>(`/cues/${id}/execute${query}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dry_run: true })
  });
}

export async function listLegacyCues(source?: "video_cues" | "sound_cues"): Promise<LegacyCueSummary[]> {
  const query = source ? `?source=${encodeURIComponent(source)}` : "";
  return apiFetchJson<LegacyCueSummary[]>(`/cues/legacy${query}`);
}
