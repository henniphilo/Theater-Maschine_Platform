import type { DramaturgyDecision, PerformanceSpeaker, CuePoint } from "@/lib/types/director";
export type { PerformanceSpeaker } from "@/lib/types/director";
import type { VisualCue } from "@/lib/types/visual";

export type InszenierungStatus = "draft" | "analyzed" | "composed" | "preparing" | "ready";

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
  avatar_video_cue?: VisualCue | null;
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

export type AvatarTextSegment = {
  csv_cue_ids: string[];
  text_excerpt: string;
  char_offset?: number | null;
  /** Row order in Avatar Textzuordnung.csv (performance sequence). */
  csv_sequence_index?: number;
  start_sentence_index: number;
  end_sentence_index: number;
  avatar_layers: AvatarSpeechLayer[];
};

export type CueAnnotationKind = "light" | "sound" | "video" | "avatar" | "space";

export type CueAnnotation = {
  kind: CueAnnotationKind;
  label: string;
  projector?: string | null;
  time_sec?: number | null;
  sentence_index?: number | null;
  reason?: string | null;
};

export type ScriptCueRow = {
  sentence_index: number;
  text: string;
  annotations: CueAnnotation[];
};

export type ScriptCueOverview = {
  rows: ScriptCueRow[];
  atmosphere_timeline: CueAnnotation[];
};

export type Teil2PerformancePlan = {
  performance_speaker: PerformanceSpeaker;
  sentences: string[];
  sentence_char_starts?: number[];
  avatar_segments: AvatarTextSegment[];
  dramaturgy: DramaturgyDecision;
  atmosphere_cue_points?: CuePoint[];
  cue_overview?: ScriptCueOverview | null;
  anarchy_level_end: number;
  alignment_warnings: string[];
};

export type SceneCorpus = {
  id: string;
  title: string;
  scenes: AnimalScene[];
  script_source?: ScriptSource | null;
  script_text?: string | null;
  status: InszenierungStatus;
  prepare_phase?: string | null;
  prepare_error?: string | null;
  gesamtkonzept: Gesamtkonzept | null;
  composition: CompositionPlan | null;
  teil2_plan?: Teil2PerformancePlan | null;
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
