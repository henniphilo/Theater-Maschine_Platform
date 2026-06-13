import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";

export type ScriptSpeaker = "AI_A" | "AI_B" | "narrator";
export type ScriptStatus = "draft" | "review" | "ready";

export type ScriptBeat = {
  id: string;
  order: number;
  text: string;
  speaker: ScriptSpeaker;
  dramaturgy: DramaturgyDecision | null;
  planned_commands: OscCommand[];
  discussion_summary: string | null;
};

export type ProductionScript = {
  id: string;
  title: string;
  source_text: string;
  beats: ScriptBeat[];
  status: ScriptStatus;
};

export type WorkshopStreamEvent = {
  type:
    | "thinking"
    | "discussion_turn"
    | "dramaturgy_decision"
    | "beat_done"
    | "error"
    | "done"
    | "script_updated";
  beat_id?: string;
  beat_order?: number;
  speaker?: "openai" | "anthropic";
  content?: string;
  dramaturgy?: DramaturgyDecision;
  planned_commands?: OscCommand[];
  discussion_summary?: string;
  detail?: string;
  script?: ProductionScript;
};

export function speakerLabel(speaker: ScriptSpeaker): string {
  if (speaker === "AI_A") return "Stimme A";
  if (speaker === "AI_B") return "Stimme B";
  return "Erzähler";
}
