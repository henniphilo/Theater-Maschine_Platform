import { apiFetch, apiFetchJson } from "@/lib/api/base";
import type {
  LegacyRuleSummary,
  Rule,
  RuleCreateInput,
  RuleEvaluateResult,
  RuleUpdateInput
} from "@/lib/types/rule";

export type ListRulesParams = {
  productionId?: string;
  enabled?: boolean;
};

function detailFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export async function listRules(params: ListRulesParams = {}): Promise<Rule[]> {
  const query = new URLSearchParams();
  if (params.productionId) query.set("production_id", params.productionId);
  if (params.enabled != null) query.set("enabled", String(params.enabled));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetchJson<Rule[]>(`/rules${suffix}`);
}

export async function fetchRule(id: string, productionId?: string): Promise<Rule> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  return apiFetchJson<Rule>(`/rules/${id}${query}`);
}

export async function createRule(input: RuleCreateInput): Promise<Rule> {
  return apiFetchJson<Rule>("/rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function updateRule(id: string, input: RuleUpdateInput): Promise<Rule> {
  return apiFetchJson<Rule>(`/rules/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function deleteRule(id: string, productionId?: string): Promise<void> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  const res = await apiFetch(`/rules/${id}${query}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Löschen fehlgeschlagen" }));
    throw new Error(detailFromBody(err, "Löschen fehlgeschlagen"));
  }
}

export async function listLegacyRules(): Promise<LegacyRuleSummary[]> {
  return apiFetchJson<LegacyRuleSummary[]>("/rules/legacy");
}

export async function evaluateRules(
  productionId: string,
  body: {
    text?: string;
    tags?: string[];
    mood?: string | null;
    intensity?: number;
    previous_cue_id?: string | null;
    manual_keys?: string[];
    now_seconds?: number;
    include_legacy_json?: boolean;
    stop_after_first_match?: boolean;
    available_cues?: Array<{ id: string; tags?: string[]; group?: string; enabled?: boolean }>;
  } = {}
): Promise<RuleEvaluateResult> {
  return apiFetchJson<RuleEvaluateResult>(
    `/rules/evaluate?production_id=${encodeURIComponent(productionId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }
  );
}
