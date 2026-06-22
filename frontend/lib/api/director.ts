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

export type OscTestRequest = {
  clip_id?: string;
  sound_cue_id?: string;
  light_scene_id?: string;
  send_visual?: boolean;
  send_sound?: boolean;
  send_light?: boolean;
  opacity?: number;
  volume?: number;
  fade_time?: number;
  stagger?: boolean;
};

export type OscTestResponse = {
  sent: boolean;
  dry_run: boolean;
  target: string;
  executed: boolean;
  blocked_reason: string | null;
  messages: OscCommand[];
};

export async function postOscTest(payload: OscTestRequest = {}): Promise<OscTestResponse> {
  const res = await fetch(`${API_BASE}/director/osc-test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "OSC test failed" }));
    throw new Error(body.detail ?? "OSC test failed");
  }
  return res.json();
}

export type TechnikHoldStatus = {
  active: boolean;
  send_visual: boolean;
  send_sound: boolean;
  send_light: boolean;
  clip_id?: string | null;
  sound_cue_id?: string | null;
  light_scene_id?: string | null;
};

export type TechnikStopRequest = {
  send_visual?: boolean;
  send_sound?: boolean;
  send_light?: boolean;
};

export async function postTechnikStart(payload: OscTestRequest = {}): Promise<TechnikHoldStatus> {
  const res = await fetch(`${API_BASE}/director/technik/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Technik start failed" }));
    throw new Error(body.detail ?? "Technik start failed");
  }
  return res.json();
}

export async function postTechnikStop(payload: TechnikStopRequest = {}): Promise<TechnikHoldStatus> {
  const res = await fetch(`${API_BASE}/director/technik/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Technik stop failed" }));
    throw new Error(body.detail ?? "Technik stop failed");
  }
  return res.json();
}

export async function fetchTechnikStatus(): Promise<TechnikHoldStatus> {
  const res = await fetch(`${API_BASE}/director/technik/status`);
  if (!res.ok) throw new Error("Technik status unavailable");
  return res.json();
}

export type LightDeskStatus = {
  tcp_connected: boolean;
  scene_id: string | null;
  hold_active: boolean;
};

export async function fetchLightDeskStatus(): Promise<LightDeskStatus> {
  const res = await fetch(`${API_BASE}/director/light/status`);
  if (!res.ok) throw new Error("Light desk status unavailable");
  return res.json();
}

export async function postLightConnect(): Promise<LightDeskStatus> {
  const res = await fetch(`${API_BASE}/director/light/connect`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light connect failed" }));
    throw new Error(body.detail ?? "Light connect failed");
  }
  return res.json();
}

export async function postLightDisconnect(): Promise<LightDeskStatus> {
  const res = await fetch(`${API_BASE}/director/light/disconnect`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light disconnect failed" }));
    throw new Error(body.detail ?? "Light disconnect failed");
  }
  return res.json();
}

export async function postLightSend(lightSceneId: string): Promise<LightDeskStatus> {
  const res = await fetch(`${API_BASE}/director/light/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ light_scene_id: lightSceneId })
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light send failed" }));
    throw new Error(body.detail ?? "Light send failed");
  }
  return res.json();
}

export async function postLightHoldStart(lightSceneId: string): Promise<LightDeskStatus> {
  const res = await fetch(`${API_BASE}/director/light/hold/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ light_scene_id: lightSceneId })
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light hold failed" }));
    throw new Error(body.detail ?? "Light hold failed");
  }
  return res.json();
}

export async function postLightStop(): Promise<LightDeskStatus> {
  const res = await fetch(`${API_BASE}/director/light/stop`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light stop failed" }));
    throw new Error(body.detail ?? "Light stop failed");
  }
  return res.json();
}

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

export async function postDirectorExecuteLayered(
  decision: DramaturgyDecision,
  options?: {
    anarchy_level?: number;
    stack?: boolean;
    skip_interval_check?: boolean;
    stagger?: boolean;
  }
): Promise<ExecuteResponse> {
  const res = await fetch(`${API_BASE}/director/execute-layered`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision,
      anarchy_level: options?.anarchy_level ?? 0.5,
      stack: options?.stack ?? true,
      skip_interval_check: options?.skip_interval_check ?? true,
      stagger: options?.stagger ?? false
    })
  });
  if (!res.ok) throw new Error("Director layered execute failed");
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
