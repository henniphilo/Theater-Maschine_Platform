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
export type ProjectorMode = "single" | "all";
export type ScriptSource = "avatar_delfin_wolf";

export type AvatarSpeechLayer = {
  avatar_speech_id: string;
  avatar: string;
  video_clip_id: string;
  projector?: string | null;
  outputs?: { output_id: string; clip_id?: string | null }[];
  visual_cue?: DramaturgyDecision["visual"] | null;
};

export type CompositionMoment = {
  id: string;
  order: number;
  scene_id: string;
  text_excerpt: string;
  speaker: "AI_A" | "AI_B" | "narrator";
  speech_mode?: SpeechMode;
  avatar_speech_id?: string | null;
  avatar_video_clip_id?: string | null;
  avatar_layers?: AvatarSpeechLayer[];
  projector_mode?: ProjectorMode;
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
  script_source?: ScriptSource | null;
  script_text?: string | null;
  status: InszenierungStatus;
  gesamtkonzept: Gesamtkonzept | null;
  composition: CompositionPlan | null;
};

export type ScriptBeatPreview = {
  order: number;
  text: string;
  avatar_ids: string[];
  avatars: string[];
  is_chorus: boolean;
};

export type Teil2ScriptResponse = {
  script_source: ScriptSource;
  text: string;
  beat_count: number;
  beats_preview: ScriptBeatPreview[];
  validation_warnings: string[];
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
