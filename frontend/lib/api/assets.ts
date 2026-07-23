import { apiBaseUrl, apiFetch, apiFetchJson } from "@/lib/api/base";
import type { Asset, AssetPreview, AssetType, AssetUpdateInput } from "@/lib/types/asset";

export type ListAssetsParams = {
  productionId?: string;
  type?: AssetType;
  /** AND filter: asset must have every listed tag. */
  tagIds?: string[];
};

export type UploadAssetParams = {
  productionId: string;
  file: File;
  name?: string;
  description?: string;
  onProgress?: (ratio: number) => void;
  signal?: AbortSignal;
};

function detailFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export async function listAssets(params: ListAssetsParams = {}): Promise<Asset[]> {
  const query = new URLSearchParams();
  if (params.productionId) query.set("production_id", params.productionId);
  if (params.type) query.set("type", params.type);
  for (const tagId of params.tagIds ?? []) {
    query.append("tag_id", tagId);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetchJson<Asset[]>(`/assets${suffix}`);
}

export async function fetchAsset(id: string, productionId?: string): Promise<Asset> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  return apiFetchJson<Asset>(`/assets/${id}${query}`);
}

export async function fetchAssetPreview(id: string, productionId: string): Promise<AssetPreview> {
  const query = `?production_id=${encodeURIComponent(productionId)}`;
  return apiFetchJson<AssetPreview>(`/assets/${id}/preview${query}`);
}

export function assetContentUrl(id: string, productionId: string): string {
  const query = `production_id=${encodeURIComponent(productionId)}`;
  return `${apiBaseUrl()}/assets/${id}/content?${query}`;
}

export async function updateAsset(id: string, input: AssetUpdateInput): Promise<Asset> {
  return apiFetchJson<Asset>(`/assets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function deleteAsset(id: string, productionId?: string): Promise<void> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  const res = await apiFetch(`/assets/${id}${query}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Löschen fehlgeschlagen" }));
    throw new Error(detailFromBody(err, "Löschen fehlgeschlagen"));
  }
}

export async function attachAssetTag(
  assetId: string,
  input: { tagId?: string; name?: string },
  productionId?: string
): Promise<Asset> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  const body =
    input.tagId != null
      ? { tag_id: input.tagId }
      : { name: input.name };
  return apiFetchJson<Asset>(`/assets/${assetId}/tags${query}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

export async function detachAssetTag(
  assetId: string,
  tagId: string,
  productionId?: string
): Promise<Asset> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  return apiFetchJson<Asset>(`/assets/${assetId}/tags/${tagId}${query}`, {
    method: "DELETE"
  });
}

export function uploadAsset(params: UploadAssetParams): Promise<Asset> {
  const { productionId, file, name, description, onProgress, signal } = params;
  const form = new FormData();
  form.append("production_id", productionId);
  form.append("file", file, file.name);
  if (name?.trim()) form.append("name", name.trim());
  if (description?.trim()) form.append("description", description.trim());

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${apiBaseUrl()}/assets/upload`);
    xhr.responseType = "json";

    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable || event.total <= 0) return;
      onProgress(Math.min(1, event.loaded / event.total));
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as Asset);
        return;
      }
      const detail = detailFromBody(xhr.response, "Upload fehlgeschlagen");
      reject(new Error(detail));
    };

    xhr.onerror = () => {
      reject(new Error("Backend nicht erreichbar. Bitte «make run» starten."));
    };

    xhr.onabort = () => {
      reject(new Error("Upload abgebrochen"));
    };

    if (signal) {
      if (signal.aborted) {
        xhr.abort();
        return;
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    xhr.send(form);
  });
}
