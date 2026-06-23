export type PerformancePart = "part1_baerenklau" | "part2_delphin_to_mole";

export type Part1BaerenklauSelection = {
  part: 1;
  scene: "Bärenklau";
  script_id: string;
  beat_id: string;
  selected_by: ("Claude" | "ChatGPT")[];
  final_sounds: string[];
  final_music: string[];
  final_videos: string[];
  final_lights: string[];
  dramaturgical_reading: string;
  cue_strategy: string;
  created_at: string;
};

export type PreviewCue = {
  mode: "preview";
  part: 1;
  target_scene: "Bärenklau";
  medium: "sound" | "music" | "video" | "light";
  medium_id: string;
  projector?: "adam" | "eva" | "rz21" | null;
  duration_sec: number;
};

export type WorkshopPhase =
  | "theme_discussion"
  | "chatgpt_theme"
  | "claude_proposal"
  | "chatgpt_delta"
  | "claude_handoff"
  | "preview"
  | "final";

export function workshopPhaseLabel(phase: WorkshopPhase | undefined): string {
  switch (phase) {
    case "theme_discussion":
      return "Claude — Thema & Zitate";
    case "chatgpt_theme":
      return "ChatGPT — Reaktion";
    case "claude_proposal":
      return "Claude — Medienpaket";
    case "chatgpt_delta":
      return "ChatGPT — Verhandlung";
    case "claude_handoff":
      return "Einigung & Übergang";
    case "preview":
      return "Preview (nach Workshop)";
    case "final":
      return "Workshop fertig";
    default:
      return "Teil 1 — Dramaturgen";
  }
}

export function resolvePerformancePart(
  explicit: PerformancePart | null | undefined,
  hasPart1Selection: boolean
): PerformancePart {
  if (explicit) return explicit;
  return hasPart1Selection ? "part1_baerenklau" : "part1_baerenklau";
}
