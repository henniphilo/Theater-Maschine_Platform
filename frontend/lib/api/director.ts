const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type DirectorSafety = {
  autopilot_enabled: boolean;
  visuals_enabled: boolean;
  sound_enabled: boolean;
  lights_enabled: boolean;
  blackout_locked: boolean;
  emergency_stop_active: boolean;
};

export type DirectorStatus = {
  safety: DirectorSafety;
  active_cues: string[];
  last_event: Record<string, unknown> | null;
  last_decision: Record<string, unknown> | null;
  last_executed: boolean | null;
  last_blocked_reason: string | null;
};

export type SafetyUpdate = Partial<DirectorSafety>;

export async function fetchDirectorStatus(): Promise<DirectorStatus> {
  const res = await fetch(`${API_BASE}/director/status`);
  if (!res.ok) throw new Error("Director status unavailable");
  return res.json();
}

export async function patchDirectorSafety(update: SafetyUpdate): Promise<DirectorStatus> {
  const res = await fetch(`${API_BASE}/director/safety`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update)
  });
  if (!res.ok) throw new Error("Safety update failed");
  return res.json();
}

export async function postDirectorEmergencyStop(): Promise<DirectorStatus> {
  const res = await fetch(`${API_BASE}/director/emergency-stop`, { method: "POST" });
  if (!res.ok) throw new Error("Emergency stop failed");
  return res.json();
}

export async function postDirectorEmergencyClear(): Promise<DirectorStatus> {
  const res = await fetch(`${API_BASE}/director/emergency-clear`, { method: "POST" });
  if (!res.ok) throw new Error("Emergency clear failed");
  return res.json();
}

export async function postRecordStart(recordingId: string): Promise<{ active: boolean; recording_id: string | null }> {
  const res = await fetch(`${API_BASE}/director/record/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recording_id: recordingId })
  });
  if (!res.ok) throw new Error("Record start failed");
  return res.json();
}

export async function postRecordStop(): Promise<{ active: boolean; recording_id: string | null }> {
  const res = await fetch(`${API_BASE}/director/record/stop`, { method: "POST" });
  if (!res.ok) throw new Error("Record stop failed");
  return res.json();
}

export type DirectorStreamUpdate = {
  type: "director_update";
  event: Record<string, unknown>;
  decision: Record<string, unknown>;
  executed: boolean;
  blocked_reason: string | null;
  safety: DirectorSafety;
  active_cues: string[];
};

export function streamDirectorEvents(onUpdate: (update: DirectorStreamUpdate) => void): () => void {
  const source = new EventSource(`${API_BASE}/director/events`);
  source.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as DirectorStreamUpdate;
      if (data.type === "director_update") onUpdate(data);
    } catch {
      /* ignore malformed events */
    }
  };
  return () => source.close();
}
