import { apiFetch, apiFetchJson } from "@/lib/api/base";
import type { Tag, TagCreateInput } from "@/lib/types/tag";

export async function listTags(productionId: string): Promise<Tag[]> {
  const query = `?production_id=${encodeURIComponent(productionId)}`;
  return apiFetchJson<Tag[]>(`/tags${query}`);
}

export async function createTag(input: TagCreateInput): Promise<Tag> {
  return apiFetchJson<Tag>("/tags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function deleteTag(id: string, productionId?: string): Promise<void> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  const res = await apiFetch(`/tags/${id}${query}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Tag löschen fehlgeschlagen" }));
    const detail =
      err && typeof err === "object" && "detail" in err && typeof err.detail === "string"
        ? err.detail
        : "Tag löschen fehlgeschlagen";
    throw new Error(detail);
  }
}
