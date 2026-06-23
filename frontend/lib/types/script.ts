import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";
import type { Part1BaerenklauSelection, PerformancePart, PreviewCue, WorkshopPhase } from "@/lib/types/part1";

export type ScriptSpeaker = "AI_A" | "AI_B" | "narrator";
export type ScriptStatus = "draft" | "review" | "ready";
export type DramaturgSpeaker = "openai" | "anthropic";

export type DiscussionTurn = {
  speaker: DramaturgSpeaker;
  content: string;
  proposed_decision?: DramaturgyDecision | null;
};

export type ScriptBeat = {
  id: string;
  order: number;
  text: string;
  scene_title?: string | null;
  speaker: ScriptSpeaker;
  dramaturgy: DramaturgyDecision | null;
  planned_commands: OscCommand[];
  discussion_turns?: DiscussionTurn[];
  discussion_summary: string | null;
};

export type ProductionScript = {
  id: string;
  title: string;
  source_text: string;
  beats: ScriptBeat[];
  status: ScriptStatus;
  has_rendered_audio?: boolean;
  part1_selection?: Part1BaerenklauSelection | null;
  performance_part?: PerformancePart | null;
  teil2_corpus_id?: string | null;
};

export type WorkshopStreamEvent = {
  type:
    | "thinking"
    | "discussion_turn"
    | "preview_start"
    | "preview_end"
    | "media_selection"
    | "agreement_saved"
    | "dramaturgy_decision"
    | "beat_done"
    | "error"
    | "done"
    | "script_updated";
  beat_id?: string;
  beat_order?: number;
  speaker?: DramaturgSpeaker;
  speaker_label?: string;
  content?: string;
  dramaturgy?: DramaturgyDecision;
  planned_commands?: OscCommand[];
  discussion_turns?: DiscussionTurn[];
  discussion_summary?: string;
  preview?: PreviewCue;
  media_selection?: {
    sounds: string[];
    music: string[];
    videos: string[];
    lights: string[];
  };
  part1_selection?: Part1BaerenklauSelection;
  workshop_phase?: WorkshopPhase;
  detail?: string;
  script?: ProductionScript;
};

export function speakerLabel(speaker: ScriptSpeaker): string {
  if (speaker === "AI_A") return "Stimme A";
  if (speaker === "AI_B") return "Stimme B";
  return "Erzähler";
}

export function dramaturgSpeakerLabel(speaker: DramaturgSpeaker): string {
  if (speaker === "openai") return "ChatGPT";
  return "Claude";
}
