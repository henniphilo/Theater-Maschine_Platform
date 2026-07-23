import { apiFetch, apiFetchJson } from "@/lib/api/base";
import type {
  AdapterType,
  Device,
  DeviceConnectionTestResult,
  DeviceCreateInput,
  DeviceUpdateInput
} from "@/lib/types/device";

export type ListDevicesParams = {
  productionId?: string;
  adapterType?: AdapterType;
  enabled?: boolean;
  includeGlobal?: boolean;
};

function detailFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export async function listDevices(params: ListDevicesParams = {}): Promise<Device[]> {
  const query = new URLSearchParams();
  if (params.productionId) query.set("production_id", params.productionId);
  if (params.adapterType) query.set("adapter_type", params.adapterType);
  if (params.enabled != null) query.set("enabled", String(params.enabled));
  if (params.includeGlobal != null) query.set("include_global", String(params.includeGlobal));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetchJson<Device[]>(`/devices${suffix}`);
}

export async function fetchDevice(id: string, productionId?: string): Promise<Device> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  return apiFetchJson<Device>(`/devices/${id}${query}`);
}

export async function createDevice(input: DeviceCreateInput): Promise<Device> {
  return apiFetchJson<Device>("/devices", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function updateDevice(id: string, input: DeviceUpdateInput): Promise<Device> {
  return apiFetchJson<Device>(`/devices/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
}

export async function deleteDevice(id: string, productionId?: string): Promise<void> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  const res = await apiFetch(`/devices/${id}${query}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Löschen fehlgeschlagen" }));
    throw new Error(detailFromBody(err, "Löschen fehlgeschlagen"));
  }
}

export async function testDeviceConnection(
  id: string,
  productionId?: string
): Promise<DeviceConnectionTestResult> {
  const query = productionId ? `?production_id=${encodeURIComponent(productionId)}` : "";
  return apiFetchJson<DeviceConnectionTestResult>(`/devices/${id}/test-connection${query}`, {
    method: "POST"
  });
}
