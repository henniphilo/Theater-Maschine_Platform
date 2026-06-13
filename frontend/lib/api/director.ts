import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";

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
  last_planned_commands: OscCommand[];
  last_osc_commands: OscCommand[];
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

export type ExecuteResponse = {
  executed: boolean;
  blocked_reason: string | null;
  osc_commands: OscCommand[];
};

export async function postDirectorDialogueEvent(payload: {
  speaker: "AI_A" | "AI_B";
  text: string;
  topic?: string;
  mood?: string;
  intensity?: number;
  tags?: string[];
}): Promise<{
  event: Record<string, unknown>;
  decision: DramaturgyDecision;
  executed: boolean;
  blocked_reason: string | null;
  planned_commands: OscCommand[];
  osc_commands: OscCommand[];
}> {
  const res = await fetch(`${API_BASE}/director/dialogue-event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Director plan failed");
  return res.json();
}

export async function postDirectorExecute(
  decision: DramaturgyDecision,
  options?: { force?: boolean; stagger?: boolean }
): Promise<ExecuteResponse> {
  const res = await fetch(`${API_BASE}/director/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision,
      force: options?.force ?? false,
      stagger: options?.stagger ?? true
    })
  });
  if (!res.ok) throw new Error("Director execute failed");
  return res.json();
}

export type DirectorStreamUpdate = {
  type: "director_update";
  event: Record<string, unknown>;
  decision: Record<string, unknown>;
  executed: boolean;
  blocked_reason: string | null;
  planned_commands: OscCommand[];
  osc_commands: OscCommand[];
  safety: DirectorSafety;
  active_cues: string[];
  last_osc_commands: OscCommand[];
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
