import type { MediaCatalog } from "@/lib/types/media";
import { apiFetch } from "@/lib/api/base";

export type VideoScope = "part1" | "part2";

export type CueKind = "video" | "sound" | "light";
export type CueSource = "catalog" | "extra";

export type CueAdminVideoRow = {
  id: string;
  pixera_name: string;
  label: string;
  source: CueSource;
  dramaturgy_active: boolean;
  removed: boolean;
  projectors: string[];
  video_type: string;
};

export type CueAdminSoundRow = {
  id: string;
  label: string;
  soundname: string;
  action: string;
  midi_note: number | null;
  ableton_hint: string;
  source: CueSource;
  dramaturgy_active: boolean;
  removed: boolean;
};

export type CueAdminLightRow = {
  id: string;
  description: string;
  channels: string[];
  groups: string[];
  source: CueSource;
  dramaturgy_active: boolean;
  removed: boolean;
};

export type CueAdminResponse = {
  videos: CueAdminVideoRow[];
  sounds: CueAdminSoundRow[];
  lights: CueAdminLightRow[];
  projectors: { id: string; pixera_prefix: string; name: string; description?: string }[];
};

export async function fetchMediaCatalog(videoScope: VideoScope = "part2"): Promise<MediaCatalog> {
  const res = await apiFetch(`/media/catalog?video_scope=${videoScope}`);
  if (!res.ok) throw new Error("Media catalog unavailable");
  return res.json();
}

export async function fetchCueAdmin(): Promise<CueAdminResponse> {
  const res = await apiFetch("/media/cue-admin");
  if (!res.ok) throw new Error("Cue-Admin nicht verfügbar");
  return res.json();
}

export async function createExtraVideo(body: {
  pixera_name: string;
  label?: string;
  projectors?: string[];
  dramaturgy_active?: boolean;
}): Promise<void> {
  const res = await apiFetch("/media/cue-admin/video", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Video anlegen fehlgeschlagen");
  }
}

export async function createExtraSound(body: {
  soundname: string;
  midi_note: number;
  label?: string;
  action?: string;
  dramaturgy_active?: boolean;
}): Promise<void> {
  const res = await apiFetch("/media/cue-admin/sound", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Sound anlegen fehlgeschlagen");
  }
}

export async function createExtraLight(body: {
  id?: string;
  description?: string;
  channels?: string[];
  groups?: string[];
  dramaturgy_active?: boolean;
}): Promise<void> {
  const res = await apiFetch("/media/cue-admin/light", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Licht anlegen fehlgeschlagen");
  }
}

export async function patchCueAdmin(
  kind: CueKind,
  cueId: string,
  body: { dramaturgy_active?: boolean; removed?: boolean }
): Promise<void> {
  const res = await apiFetch(`/media/cue-admin/${kind}/${encodeURIComponent(cueId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Änderung fehlgeschlagen");
  }
}

export async function deleteExtraCue(kind: CueKind, cueId: string): Promise<void> {
  const res = await apiFetch(`/media/cue-admin/${kind}/${encodeURIComponent(cueId)}`, {
    method: "DELETE"
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Löschen fehlgeschlagen");
  }
}
