import type { VisualCue } from "@/lib/types/visual";

export type CommandTraceMeta = {
  logical_signal_id: string;
  command_id: string;
  run_id?: string | null;
  run_epoch?: number | null;
  http_request_id?: string | null;
};

export type TraceContext = {
  frontend_run_id?: string;
  frontend_generation?: number;
  source?: string;
  trigger?: string;
  cue_point_key?: string;
  segment_key?: string;
  frontend_route?: string;
};

export type OscCommand = {
  bridge: string;
  host: string;
  port: number;
  address: string;
  args: unknown[];
  dry_run: boolean;
  mirror?: boolean;
  trace?: CommandTraceMeta | null;
};


export type CuePoint = {
  trigger: string;
  keyword?: string | null;
  sentence_index?: number | null;
  time_offset_sec?: number;
  function?: string;
  intensity?: number;
  visual?: DramaturgyDecision["visual"];
  sound?: DramaturgyDecision["sound"];
  light?: DramaturgyDecision["light"];
};

export type PerformanceSpeaker = "AI_A" | "AI_B" | "narrator";

export type DramaturgyDecision = {
  visual?: VisualCue | null;
  sound?: {
    action: string;
    cue_id?: string | null;
    volume?: number;
  } | null;
  light?: {
    action: string;
    scene_id?: string | null;
    scene_ids?: string[];
    fade_time?: number;
    intensity?: number | null;
    replace_previous?: boolean;
  } | null;
  reason: string;
  reason_short?: string;
  dramaturgical_reading?: string;
  dramaturgical_function?: string;
  decision_kind?: string;
  confidence?: number;
  cue_points?: CuePoint[];
  performance_speakers?: PerformanceSpeaker[];
  tags: string[];
  mood: string;
  intensity: number;
  timestamp: number;
};

export type DirectorPayload = {
  event: Record<string, unknown>;
  decision: DramaturgyDecision;
  executed: boolean;
  blocked_reason: string | null;
  planned_commands: OscCommand[];
  osc_commands: OscCommand[];
};

export type ShowPhase =
  | "planned"
  | "dramaturg_discussion"
  | "speaking"
  | "cues_active"
  | "sent"
  | "blocked";

export function formatOscCommand(cmd: OscCommand): string {
  const args = cmd.args.length ? ` ${cmd.args.map((a) => JSON.stringify(a)).join(" ")}` : "";
  const mode = cmd.dry_run ? "DRY-RUN" : "SEND";
  const transport = cmd.address.startsWith("tcp/") ? "TCP" : "OSC";
  const mirror = cmd.mirror ? " mirror" : "";
  return `[${mode}] [${cmd.bridge}/${transport}${mirror}] → ${cmd.host}:${cmd.port} ${cmd.address}${args}`;
}
