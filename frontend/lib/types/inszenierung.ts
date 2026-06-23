import type { DramaturgyDecision } from "@/lib/types/director";

export type InszenierungStatus = "draft" | "analyzed" | "composed" | "ready";

export type AnimalScene = {
  id: string;
  animal: string;
  title: string;
  source_text: string;
  play_reference?: string | null;
};

export type AnimalPosition = {
  animal: string;
  stance: string;
  money_angle: string;
};

export type CrossSceneLink = {
  label: string;
  scene_ids: string[];
  note: string;
};

export type AnarchyCurve = {
  start: number;
  end: number;
};

export type Gesamtkonzept = {
  thesis: string;
  money_themes: string[];
  animal_positions: AnimalPosition[];
  cross_scene_links: CrossSceneLink[];
  anarchy_curve: AnarchyCurve;
  discussion_summary?: string | null;
};

export type SpeechMode = "tts" | "avatar_video" | "silent";

export type CompositionMoment = {
  id: string;
  order: number;
  scene_id: string;
  text_excerpt: string;
  speaker: "AI_A" | "AI_B" | "narrator";
  speech_mode?: SpeechMode;
  avatar_speech_id?: string | null;
  avatar_video_clip_id?: string | null;
  dramaturgy?: DramaturgyDecision | null;
  overlap_with_previous: number;
  anarchy_level: number;
  start_delay_ms: number;
  duration_hint_ms?: number | null;
};

export type CompositionPlan = {
  moments: CompositionMoment[];
  total_estimated_duration_sec: number;
  max_concurrent_voices: number;
  max_concurrent_videos: number;
};

export type SceneCorpus = {
  id: string;
  title: string;
  scenes: AnimalScene[];
  status: InszenierungStatus;
  gesamtkonzept: Gesamtkonzept | null;
  composition: CompositionPlan | null;
};

export type AnalyseStreamEvent = {
  type: "thinking" | "discussion_turn" | "gesamtkonzept" | "corpus_updated" | "error" | "done";
  speaker?: string;
  content?: string;
  gesamtkonzept?: Gesamtkonzept;
  corpus?: SceneCorpus;
  detail?: string;
};

export type KompositionStreamEvent = {
  type: "thinking" | "moment" | "composition_plan" | "corpus_updated" | "error" | "done";
  moment?: CompositionMoment;
  moment_order?: number;
  composition?: CompositionPlan;
  corpus?: SceneCorpus;
  detail?: string;
};
