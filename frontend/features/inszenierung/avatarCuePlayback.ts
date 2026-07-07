import type { AvatarTextSegment, CompositionMoment, CompositionPlan, Teil2PerformancePlan } from "@/lib/types/inszenierung";
import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";
import type { VisualCue } from "@/lib/types/visual";
import { isDirectorPerformanceAborted, postDirectorExecuteLayered } from "@/lib/api/director";
import { waitWhilePlaybackPaused } from "@/lib/api/client";

let avatarFireChain: Promise<void> = Promise.resolve();

const AVATAR_POSITION_DEBOUNCE_MS = 150;
let avatarPositionTimer: ReturnType<typeof setTimeout> | null = null;

type PendingAvatarPositionFire = {
  plan: Teil2PerformancePlan;
  globalPos: number;
  fired: Set<string>;
  sentenceCharStarts: number[];
  anarchyLevelFor: (segment: AvatarTextSegment) => number;
  onCommands: (commands: OscCommand[]) => Promise<void>;
  shouldAbort: () => boolean;
  onSegmentFired?: (segment: AvatarTextSegment) => void;
};

let pendingAvatarPositionFire: PendingAvatarPositionFire | null = null;

function withAvatarFireLock<T>(work: () => Promise<T>): Promise<T> {
  const run = avatarFireChain.then(work, work);
  avatarFireChain = run.then(
    () => undefined,
    () => undefined
  );
  return run;
}

export async function executeAvatarVisualCue(
  visual: VisualCue,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  textExcerpt?: string
): Promise<boolean> {
  if (shouldAbort() || isDirectorPerformanceAborted()) return false;
  const decision: DramaturgyDecision = {
    reason: "Avatar-Sprache",
    tags: ["teil2", "avatar"],
    mood: "tension",
    intensity: anarchyLevel,
    visual,
    timestamp: Date.now()
  };
  try {
    const result = await postDirectorExecuteLayered(decision, {
      anarchy_level: anarchyLevel,
      stack: false,
      skip_interval_check: true,
      stagger: false,
      text_excerpt: textExcerpt
    });
    if (shouldAbort() || isDirectorPerformanceAborted()) return false;
    if (!result.executed) {
      console.warn(
        "[avatar] cue blocked:",
        result.blocked_reason ?? "executed=false",
        visual.clip_id,
        textExcerpt ? `«${textExcerpt.slice(0, 40)}»` : ""
      );
    }
    if (result.osc_commands.length > 0) {
      void onCommands(result.osc_commands).catch((err) => {
        console.warn("Avatar cue highlight failed (playback continues):", err);
      });
    }
    return result.executed;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return false;
    console.warn("Avatar cue failed (playback continues):", err);
    return false;
  }
}

export function avatarVisualCuesForMoment(moment: CompositionMoment): VisualCue[] {
  const fromLayers = (moment.avatar_layers ?? [])
    .map((layer) => layer.visual_cue)
    .filter((cue): cue is VisualCue => Boolean(cue));
  if (fromLayers.length > 0) return fromLayers;
  if (moment.avatar_video_cue) return [moment.avatar_video_cue];
  return [];
}

export function sentenceSpanLength(
  sentenceIndex: number,
  sentenceCharStarts: number[],
  scriptTextLength: number
): number {
  const start = sentenceCharStarts[sentenceIndex] ?? 0;
  const end =
    sentenceIndex + 1 < sentenceCharStarts.length
      ? sentenceCharStarts[sentenceIndex + 1]!
      : scriptTextLength;
  return Math.max(1, end - start);
}

export async function fireAvatarSegmentIfDue(
  segment: AvatarTextSegment,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<boolean> {
  if (shouldAbort()) return false;
  if (!(await waitWhilePlaybackPaused(shouldAbort))) return false;
  let anySent = false;
  for (const layer of segment.avatar_layers) {
    if (!layer.visual_cue) continue;
    if (shouldAbort()) return anySent;
    const sent = await executeAvatarVisualCue(
      layer.visual_cue,
      anarchyLevel,
      onCommands,
      shouldAbort,
      segment.text_excerpt
    );
    anySent = anySent || sent;
  }
  return anySent;
}

export async function fireAvatarSegmentCues(
  segment: AvatarTextSegment,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<void> {
  await fireAvatarSegmentIfDue(segment, anarchyLevel, onCommands, shouldAbort);
}

export async function fireAvatarMomentCues(
  moment: CompositionMoment,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<void> {
  for (const visual of avatarVisualCuesForMoment(moment)) {
    if (shouldAbort()) return;
    await executeAvatarVisualCue(visual, anarchyLevel, onCommands, shouldAbort, moment.text_excerpt);
  }
}

export function momentNeedsAvatarVisualRefresh(moment: CompositionMoment): boolean {
  if ((moment.speech_mode ?? "tts") !== "avatar_video") return false;
  if (!moment.avatar_layers?.length && !moment.avatar_speech_id && !moment.avatar_video_clip_id) {
    return false;
  }
  return avatarVisualCuesForMoment(moment).length === 0;
}

export function planNeedsAvatarVisualRefresh(plan: CompositionPlan): boolean {
  return plan.moments.some((moment) => momentNeedsAvatarVisualRefresh(moment));
}

export function planRequiresTts(plan: CompositionPlan): boolean {
  return plan.moments.some((moment) => (moment.speech_mode ?? "tts") === "tts");
}

export function teil2PlanRequiresTts(): boolean {
  return true;
}

export function avatarSegmentKey(segment: AvatarTextSegment): string {
  if (segment.char_offset != null) return `offset:${segment.char_offset}`;
  return `sentence:${segment.start_sentence_index}:${segment.csv_cue_ids.join(",")}`;
}

export function resolveSentenceCharStarts(plan: Teil2PerformancePlan, scriptText: string): number[] {
  if (
    plan.sentence_char_starts?.length === plan.sentences.length &&
    plan.sentence_char_starts.length > 0
  ) {
    return plan.sentence_char_starts;
  }
  const starts: number[] = [];
  let searchFrom = 0;
  for (const sentence of plan.sentences) {
    const stripped = sentence.trim();
    let start = scriptText.indexOf(stripped, searchFrom);
    if (start < 0 && stripped.length > 12) {
      start = scriptText.indexOf(stripped.slice(0, Math.min(32, stripped.length)), searchFrom);
    }
    if (start < 0) start = searchFrom;
    starts.push(start);
    searchFrom = Math.max(searchFrom, start + stripped.length);
  }
  return starts;
}

export function effectiveCharOffset(segment: AvatarTextSegment, sentenceCharStarts: number[]): number {
  if (segment.char_offset != null) return segment.char_offset;
  return sentenceCharStarts[segment.start_sentence_index] ?? 0;
}

export function avatarSegmentsInSentence(
  plan: Teil2PerformancePlan,
  sentenceIndex: number,
  sentenceCharStarts: number[],
  scriptTextLength: number
): AvatarTextSegment[] {
  const sentenceStart = sentenceCharStarts[sentenceIndex] ?? 0;
  const sentenceEnd =
    sentenceIndex + 1 < sentenceCharStarts.length
      ? sentenceCharStarts[sentenceIndex + 1]!
      : scriptTextLength;
  return plan.avatar_segments
    .filter((segment) => {
      const offset = effectiveCharOffset(segment, sentenceCharStarts);
      return offset >= sentenceStart && offset < sentenceEnd;
    })
    .sort(
      (a, b) =>
        effectiveCharOffset(a, sentenceCharStarts) - effectiveCharOffset(b, sentenceCharStarts)
    );
}

export function avatarSegmentsDueAtPosition(
  plan: Teil2PerformancePlan,
  globalPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[]
): AvatarTextSegment[] {
  return plan.avatar_segments
    .filter((segment) => {
      if (fired.has(avatarSegmentKey(segment))) return false;
      return globalPos >= effectiveCharOffset(segment, sentenceCharStarts);
    })
    .sort(
      (a, b) =>
        effectiveCharOffset(a, sentenceCharStarts) - effectiveCharOffset(b, sentenceCharStarts)
    );
}

export function scheduleAvatarSegmentsAtPosition(
  plan: Teil2PerformancePlan,
  globalPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[],
  anarchyLevelFor: (segment: AvatarTextSegment) => number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void
): void {
  pendingAvatarPositionFire = {
    plan,
    globalPos,
    fired,
    sentenceCharStarts,
    anarchyLevelFor,
    onCommands,
    shouldAbort,
    onSegmentFired
  };
  if (avatarPositionTimer !== null) return;
  avatarPositionTimer = setTimeout(() => {
    avatarPositionTimer = null;
    const pending = pendingAvatarPositionFire;
    pendingAvatarPositionFire = null;
    if (!pending || pending.shouldAbort()) return;
    void fireAvatarSegmentsAtPosition(
      pending.plan,
      pending.globalPos,
      pending.fired,
      pending.sentenceCharStarts,
      pending.anarchyLevelFor,
      pending.onCommands,
      pending.shouldAbort,
      pending.onSegmentFired
    );
  }, AVATAR_POSITION_DEBOUNCE_MS);
}

export async function fireAvatarSegmentsAtPosition(
  plan: Teil2PerformancePlan,
  globalPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[],
  anarchyLevelFor: (segment: AvatarTextSegment) => number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void
): Promise<void> {
  await withAvatarFireLock(async () => {
    let due = avatarSegmentsDueAtPosition(plan, globalPos, fired, sentenceCharStarts);
    while (due.length > 0) {
      const segment = due[0]!;
      if (shouldAbort()) return;
      const sent = await fireAvatarSegmentIfDue(
        segment,
        anarchyLevelFor(segment),
        onCommands,
        shouldAbort
      );
      if (!sent) break;
      fired.add(avatarSegmentKey(segment));
      onSegmentFired?.(segment);
      due = avatarSegmentsDueAtPosition(plan, globalPos, fired, sentenceCharStarts);
    }
  });
}

export async function fireInitialAvatarSegments(
  plan: Teil2PerformancePlan,
  fired: Set<string>,
  sentenceCharStarts: number[],
  anarchyLevelFor: (segment: AvatarTextSegment) => number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void
): Promise<void> {
  await fireAvatarSegmentsAtPosition(
    plan,
    0,
    fired,
    sentenceCharStarts,
    anarchyLevelFor,
    onCommands,
    shouldAbort,
    onSegmentFired
  );
}

export async function fireRemainingSentenceSegments(
  plan: Teil2PerformancePlan,
  sentenceIndex: number,
  fired: Set<string>,
  sentenceCharStarts: number[],
  scriptTextLength: number,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void
): Promise<void> {
  await withAvatarFireLock(async () => {
    for (const segment of avatarSegmentsInSentence(
      plan,
      sentenceIndex,
      sentenceCharStarts,
      scriptTextLength
    )) {
      if (fired.has(avatarSegmentKey(segment))) continue;
      if (shouldAbort()) return;
      const sent = await fireAvatarSegmentIfDue(segment, anarchyLevel, onCommands, shouldAbort);
      if (!sent) continue;
      fired.add(avatarSegmentKey(segment));
      onSegmentFired?.(segment);
    }
  });
}
export async function fireAllRemainingAvatarSegments(
  plan: Teil2PerformancePlan,
  fired: Set<string>,
  sentenceCharStarts: number[],
  anarchyLevelFor: (segment: AvatarTextSegment) => number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void
): Promise<void> {
  const remaining = [...plan.avatar_segments].sort(
    (a, b) =>
      effectiveCharOffset(a, sentenceCharStarts) - effectiveCharOffset(b, sentenceCharStarts)
  );
  await withAvatarFireLock(async () => {
    for (const segment of remaining) {
      if (fired.has(avatarSegmentKey(segment))) continue;
      if (shouldAbort()) return;
      const sent = await fireAvatarSegmentIfDue(
        segment,
        anarchyLevelFor(segment),
        onCommands,
        shouldAbort
      );
      if (!sent) continue;
      fired.add(avatarSegmentKey(segment));
      onSegmentFired?.(segment);
    }
  });
}
