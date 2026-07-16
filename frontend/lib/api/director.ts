import type { DramaturgyDecision, OscCommand, TraceContext } from "@/lib/types/director";

import { apiBaseUrl, apiFetch } from "@/lib/api/base";
import {
  buildTraceContext,
  logSignalTraceEvent,
  startFrontendPlaybackTrace
} from "@/lib/debug/signalTrace";
import {
  noteDesiredPerformanceTryout,
  peekDesiredPerformanceTryout
} from "@/lib/performanceTryout";

export { buildTraceContext, logSignalTraceEvent, startFrontendPlaybackTrace };

let performanceOscAbort: AbortController | null = null;

/** Serializes safety patches so a late mount-sync(false) cannot overwrite Probebetrieb. */
let safetyPatchTail: Promise<unknown> = Promise.resolve();

/** In-flight emergency stops — arm waits so a late stop cannot undo Probebetrieb. */
let stopTail: Promise<unknown> = Promise.resolve();

export function isDirectorPerformanceAborted(): boolean {
  return performanceOscAbort?.signal.aborted ?? false;
}

export async function syncPerformanceTryoutToDirector(tryout: boolean): Promise<DirectorStatus> {
  noteDesiredPerformanceTryout(tryout);
  const run = safetyPatchTail.then(async () => {
    // Re-read desired value: an older in-flight call must not apply a stale false.
    const desired = peekDesiredPerformanceTryout();
    return patchDirectorSafety({
      lights_enabled: !desired,
      performance_tryout: desired
    });
  });
  safetyPatchTail = run.then(
    () => undefined,
    () => undefined
  );
  return run;
}

/** Re-enable director outputs and reset abort handle before a performance run. */
export async function armDirectorForPerformance(options?: { tryout?: boolean }): Promise<void> {
  // Finish any Stop/emergency before clearing — otherwise a late emergency_stop
  // leaves emergency_stop_active stuck and can race Probebetrieb off.
  await stopTail;
  performanceOscAbort?.abort();
  performanceOscAbort = new AbortController();
  if (options?.tryout != null) {
    noteDesiredPerformanceTryout(options.tryout);
  } else {
    noteDesiredPerformanceTryout(peekDesiredPerformanceTryout());
  }
  const tryout = peekDesiredPerformanceTryout();
  logSignalTraceEvent(
    "frontend.playback_started",
    { source: "armDirectorForPerformance", tryout },
    { status: "arm" }
  );
  await postDirectorEmergencyClear();
  const run = safetyPatchTail.then(async () => {
    const desired = peekDesiredPerformanceTryout();
    return patchDirectorSafety({
      autopilot_enabled: true,
      visuals_enabled: true,
      sound_enabled: true,
      lights_enabled: !desired,
      performance_tryout: desired
    });
  });
  safetyPatchTail = run.then(
    () => undefined,
    () => undefined
  );
  const status = await run;
  const desired = peekDesiredPerformanceTryout();
  if (status.safety.performance_tryout !== desired || status.safety.lights_enabled !== !desired) {
    throw new Error(
      `Probebetrieb am Director nicht gesetzt (tryout=${status.safety.performance_tryout}, lights=${status.safety.lights_enabled})`
    );
  }
}

/** Cancel in-flight cue requests and block further OSC during performance stop. */
export async function stopDirectorPerformance(): Promise<void> {
  logSignalTraceEvent("frontend.stop_requested", {}, { status: "stop_requested" });
  performanceOscAbort?.abort();
  performanceOscAbort = null;
  const run = stopTail.then(() => postDirectorEmergencyStop());
  stopTail = run.then(
    () => undefined,
    () => undefined
  );
  await run;
}

function directorPerformanceSignal(): AbortSignal | undefined {
  return performanceOscAbort?.signal;
}

export type DirectorSafety = {
  autopilot_enabled: boolean;
  visuals_enabled: boolean;
  sound_enabled: boolean;
  lights_enabled: boolean;
  blackout_locked: boolean;
  emergency_stop_active: boolean;
  performance_tryout: boolean;
};

export type DirectorStatus = {
  safety: DirectorSafety;
  active_cues: string[];
  osc_queue_depth?: number;
  run_id?: string | null;
  run_epoch?: number;
  last_event: Record<string, unknown> | null;
  last_decision: Record<string, unknown> | null;
  last_executed: boolean | null;
  last_blocked_reason: string | null;
  last_planned_commands: OscCommand[];
  last_osc_commands: OscCommand[];
};

export type SafetyUpdate = Partial<DirectorSafety>;

export async function fetchDirectorStatus(): Promise<DirectorStatus> {
  const res = await apiFetch("/director/status");
  if (!res.ok) throw new Error("Director status unavailable");
  return res.json();
}

export async function patchDirectorSafety(update: SafetyUpdate): Promise<DirectorStatus> {
  const res = await apiFetch("/director/safety", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update)
  });
  if (!res.ok) throw new Error("Safety update failed");
  return res.json();
}

export async function postDirectorEmergencyStop(): Promise<DirectorStatus> {
  const res = await apiFetch("/director/emergency-stop", { method: "POST" });
  if (!res.ok) throw new Error("Emergency stop failed");
  return res.json();
}

export async function postDirectorEmergencyClear(): Promise<DirectorStatus> {
  const res = await apiFetch("/director/emergency-clear", { method: "POST" });
  if (!res.ok) throw new Error("Emergency clear failed");
  return res.json();
}

export async function postRecordStart(recordingId: string): Promise<{ active: boolean; recording_id: string | null }> {
  const res = await apiFetch("/director/record/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recording_id: recordingId })
  });
  if (!res.ok) throw new Error("Record start failed");
  return res.json();
}

export async function postRecordStop(): Promise<{ active: boolean; recording_id: string | null }> {
  const res = await apiFetch("/director/record/stop", { method: "POST" });
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
  const res = await apiFetch("/director/osc-test", {
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
  const res = await apiFetch("/director/technik/start", {
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
  const res = await apiFetch("/director/technik/stop", {
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
  const res = await apiFetch("/director/technik/status");
  if (!res.ok) throw new Error("Technik status unavailable");
  return res.json();
}

export type LightDeskStatus = {
  tcp_connected: boolean;
  scene_id: string | null;
  hold_active: boolean;
  intensity: number | null;
};

export type LightSendRequest = {
  light_scene_id: string;
  intensity?: number | null;
};

export async function fetchLightDeskStatus(): Promise<LightDeskStatus> {
  const res = await apiFetch("/director/light/status");
  if (!res.ok) throw new Error("Light desk status unavailable");
  return res.json();
}

export async function postLightConnect(): Promise<LightDeskStatus> {
  const res = await apiFetch("/director/light/connect", { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light connect failed" }));
    throw new Error(body.detail ?? "Light connect failed");
  }
  return res.json();
}

export async function postLightDisconnect(): Promise<LightDeskStatus> {
  const res = await apiFetch("/director/light/disconnect", { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light disconnect failed" }));
    throw new Error(body.detail ?? "Light disconnect failed");
  }
  return res.json();
}

export async function postLightSend(
  lightSceneId: string,
  options: { intensity?: number | null } = {}
): Promise<LightDeskStatus> {
  const body: LightSendRequest = { light_scene_id: lightSceneId };
  if (options.intensity != null) {
    body.intensity = options.intensity;
  }
  const res = await apiFetch("/director/light/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light send failed" }));
    throw new Error(body.detail ?? "Light send failed");
  }
  return res.json();
}

export async function postLightHoldStart(
  lightSceneId: string,
  options: { intensity?: number | null } = {}
): Promise<LightDeskStatus> {
  const body: LightSendRequest = { light_scene_id: lightSceneId };
  if (options.intensity != null) {
    body.intensity = options.intensity;
  }
  const res = await apiFetch("/director/light/hold/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Light hold failed" }));
    throw new Error(body.detail ?? "Light hold failed");
  }
  return res.json();
}

export async function postLightStop(): Promise<LightDeskStatus> {
  const res = await apiFetch("/director/light/stop", { method: "POST" });
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
  const res = await apiFetch("/director/dialogue-event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Director plan failed");
  return res.json();
}

async function directorExecuteFetch(
  path: string,
  body: Record<string, unknown>,
  errorMessage: string
): Promise<ExecuteResponse> {
  const trace = buildTraceContext(
    typeof body.trace === "object" && body.trace !== null
      ? (body.trace as TraceContext)
      : undefined
  );
  const payload = trace ? { ...body, trace } : body;
  logSignalTraceEvent(
    "frontend.request_started",
    { source: trace?.source, trigger: trace?.trigger, route: path },
    { status: "started" }
  );
  try {
    const res = await apiFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: directorPerformanceSignal()
    });
    if (!res.ok) throw new Error(errorMessage);
    const data = (await res.json()) as ExecuteResponse;
    logSignalTraceEvent(
      "frontend.request_completed",
      {
        executed: data.executed,
        blocked_reason: data.blocked_reason,
        route: path
      },
      { status: "completed" }
    );
    return data;
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      logSignalTraceEvent(
        "frontend.request_aborted",
        { route: path, abort_seen: true },
        { status: "aborted" }
      );
    }
    throw err;
  }
}

export async function postDirectorExecute(
  decision: DramaturgyDecision,
  options?: { force?: boolean; stagger?: boolean; trace?: TraceContext }
): Promise<ExecuteResponse> {
  return directorExecuteFetch(
    "/director/execute",
    {
      decision,
      force: options?.force ?? false,
      stagger: options?.stagger ?? true,
      trace: options?.trace
    },
    "Director execute failed"
  );
}

export async function postDirectorExecuteLayered(
  decision: DramaturgyDecision,
  options?: {
    anarchy_level?: number;
    stack?: boolean;
    skip_interval_check?: boolean;
    stagger?: boolean;
    text_excerpt?: string;
    trace?: TraceContext;
  }
): Promise<ExecuteResponse> {
  return directorExecuteFetch(
    "/director/execute-layered",
    {
      decision,
      anarchy_level: options?.anarchy_level ?? 0.5,
      stack: options?.stack ?? true,
      skip_interval_check: options?.skip_interval_check ?? true,
      stagger: options?.stagger ?? false,
      text_excerpt: options?.text_excerpt,
      trace: options?.trace
    },
    "Director layered execute failed"
  );
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
  const source = new EventSource(`${apiBaseUrl()}/director/events`);
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

export type OscLogRecentResponse = {
  lines: string[];
  path: string;
  limit: number;
};

/** Last lines from backend logs/osc.log (same text as the terminal OSC/MIDI feed). */
export async function fetchOscLogRecent(limit = 150): Promise<OscLogRecentResponse> {
  const res = await apiFetch(`/director/osc-log/recent?limit=${Math.max(1, Math.min(limit, 500))}`);
  if (!res.ok) throw new Error("OSC-Log nicht erreichbar");
  return res.json();
}

export type RemoteTransportAction = "play" | "pause" | "stop";

export type RemoteTransportPendingCommand = {
  id: string;
  action: RemoteTransportAction;
  created_at: number;
};

export type RemoteTransportStatus = {
  pending: RemoteTransportPendingCommand | null;
  listener_connected: boolean;
  listener_heartbeat_age_sec: number | null;
};

export type RemoteTransportPostResult = {
  id: string;
  action: RemoteTransportAction;
  listener_connected: boolean;
};

export async function postRemoteTransport(
  action: RemoteTransportAction
): Promise<RemoteTransportPostResult> {
  const res = await apiFetch("/director/remote-transport", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action })
  });
  if (!res.ok) throw new Error("Remote-Transport fehlgeschlagen");
  return res.json();
}

export async function pollRemoteTransport(options?: {
  consume?: boolean;
  heartbeat?: boolean;
}): Promise<RemoteTransportStatus> {
  const params = new URLSearchParams();
  if (options?.consume) params.set("consume", "1");
  if (options?.heartbeat) params.set("heartbeat", "1");
  const qs = params.toString();
  const res = await apiFetch(`/director/remote-transport${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error("Remote-Transport Status fehlgeschlagen");
  return res.json();
}
