export type CueType =
  | "video"
  | "audio"
  | "light"
  | "osc"
  | "midi"
  | "text"
  | "wait";

export const CUE_TYPES: CueType[] = [
  "video",
  "audio",
  "light",
  "osc",
  "midi",
  "text",
  "wait"
];

export const CUE_ACTIONS: Record<CueType, string[]> = {
  video: ["play_clip", "stop_clip", "fade_to_black"],
  audio: ["trigger_cue", "stop_cue", "set_volume"],
  light: ["set_scene", "fade_blackout", "pulse"],
  osc: ["send"],
  midi: ["note_on", "note_off", "trigger_cue"],
  text: ["show", "clear"],
  wait: ["wait"]
};

export type Cue = {
  id: string;
  production_id: string;
  name: string;
  cue_type: CueType;
  asset_id: string | null;
  device_id: string | null;
  action: string;
  parameters: Record<string, unknown>;
  enabled: boolean;
  priority: number;
  cooldown_seconds: number | null;
  created_at: string;
  updated_at: string;
};

export type CueCreateInput = {
  production_id: string;
  name: string;
  cue_type: CueType;
  action: string;
  asset_id?: string | null;
  device_id?: string | null;
  parameters?: Record<string, unknown>;
  enabled?: boolean;
  priority?: number;
  cooldown_seconds?: number | null;
};

export type CueUpdateInput = {
  name?: string;
  cue_type?: CueType;
  action?: string;
  asset_id?: string | null;
  device_id?: string | null;
  parameters?: Record<string, unknown>;
  enabled?: boolean;
  priority?: number;
  cooldown_seconds?: number | null;
  clear_asset_id?: boolean;
  clear_device_id?: boolean;
  clear_cooldown_seconds?: boolean;
};

export type CueExecutionResult = {
  cue_id: string;
  production_id: string;
  dry_run: boolean;
  status: "planned" | "skipped" | "rejected";
  message: string;
  planned: Record<string, unknown>;
};

export type LegacyCueSummary = {
  source: "video_cues" | "sound_cues";
  catalog_id: string;
  label: string;
  cue_type: CueType;
  suggested_action: string;
  details: Record<string, unknown>;
};

/** Sensible default parameters for the cue editor. */
export function defaultParametersFor(type: CueType): Record<string, unknown> {
  switch (type) {
    case "video":
      return { clip_id: "", projector: null, video_type: "atmosphere", fade_time: 4, opacity: 0.8 };
    case "audio":
      return { catalog_cue_id: "", volume: 0.6 };
    case "light":
      return { scene_id: "", fade_time: 4 };
    case "osc":
      return { address: "/example", args: [] };
    case "midi":
      return { note: 60, channel: 1, velocity: 100 };
    case "text":
      return { content: "" };
    case "wait":
      return { duration_seconds: 1 };
    default:
      return {};
  }
}
