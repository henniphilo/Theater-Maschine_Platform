import { apiFetchJson } from "@/lib/api/base";
import type { ActiveProduction, Production, ProductionCreateInput } from "@/lib/types/production";

export async function listProductions(includeArchived = true): Promise<Production[]> {
  const q = includeArchived ? "" : "?include_archived=false";
  return apiFetchJson<Production[]>(`/productions${q}`);
}

export async function createProduction(input: ProductionCreateInput): Promise<Production> {
  return apiFetchJson<Production>("/productions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function fetchProduction(id: string): Promise<Production> {
  return apiFetchJson<Production>(`/productions/${id}`);
}

export async function archiveProduction(id: string): Promise<Production> {
  return apiFetchJson<Production>(`/productions/${id}/archive`, { method: "POST" });
}

export async function fetchActiveProduction(): Promise<ActiveProduction> {
  return apiFetchJson<ActiveProduction>("/productions/active");
}

export async function setActiveProduction(productionId: string | null): Promise<ActiveProduction> {
  return apiFetchJson<ActiveProduction>("/productions/active", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ production_id: productionId })
  });
}
