import type { AvatarTextSegment, CompositionMoment, CompositionPlan, Teil2PerformancePlan } from "@/lib/types/inszenierung";
import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";
import type { VisualCue } from "@/lib/types/visual";
import { isDirectorPerformanceAborted, isAvatarDoneGateEnabled, postDirectorExecuteLayered, waitForAvatarVideosDone, type AvatarDoneWaitResult } from "@/lib/api/director";
import { setPlaybackPaused, waitWhilePlaybackPaused } from "@/lib/api/client";

let avatarFireChain: Promise<void> = Promise.resolve();

const AVATAR_POSITION_DEBOUNCE_MS = 150;
const DEFAULT_AVATAR_DONE_TIMEOUT_MS = 120_000;
const AVATAR_DONE_TIMEOUT_GRACE_MS = 2_000;
let avatarPositionTimer: ReturnType<typeof setTimeout> | null = null;

/** In-flight avatar clip(s): TTS stays parallel; on done the next clip starts immediately. */
type PendingAvatarDone = {
  cueNames: string[];
  timeoutMs: number;
  finished: Promise<AvatarDoneWaitResult | null>;
  token: symbol;
};

let pendingAvatarDone: PendingAvatarDone | null = null;

export type AvatarChainContext = {
  plan: Teil2PerformancePlan;
  fired: Set<string>;
  sentenceCharStarts: number[];
  scriptText: string;
  anarchyLevelFor: (segment: AvatarTextSegment) => number;
  onCommands: (commands: OscCommand[]) => Promise<void>;
  shouldAbort: () => boolean;
  onSegmentFired?: (segment: AvatarTextSegment) => void;
};

let avatarChainContext: AvatarChainContext | null = null;

type PendingAvatarPositionFire = {
  plan: Teil2PerformancePlan;
  globalPos: number;
  fired: Set<string>;
  sentenceCharStarts: number[];
  scriptText: string;
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
): Promise<{ executed: boolean; cueNames: string[] }> {
  if (shouldAbort() || isDirectorPerformanceAborted()) return { executed: false, cueNames: [] };
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
    if (shouldAbort() || isDirectorPerformanceAborted()) return { executed: false, cueNames: [] };
    if (!result.executed) {
      console.warn(
        "[avatar] cue blocked:",
        result.blocked_reason ?? "executed=false",
        visual.clip_id,
        textExcerpt ? `«${textExcerpt.slice(0, 40)}»` : ""
      );
    }
    const cueNames = pixeraCueNamesFromCommands(result.osc_commands);
    if (result.osc_commands.length > 0) {
      void onCommands(result.osc_commands).catch((err) => {
        console.warn("Avatar cue highlight failed (playback continues):", err);
      });
    }
    return { executed: result.executed, cueNames };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return { executed: false, cueNames: [] };
    console.warn("Avatar cue failed (playback continues):", err);
    return { executed: false, cueNames: [] };
  }
}

function pixeraCueNamesFromCommands(commands: OscCommand[]): string[] {
  const names: string[] = [];
  for (const cmd of commands) {
    if (cmd.bridge !== "pixera") continue;
    const raw = cmd.args?.[0];
    if (typeof raw === "string" && raw.trim()) names.push(raw.trim());
  }
  return names;
}

function avatarDoneTimeoutMs(segment: AvatarTextSegment): number {
  const durations = segment.avatar_layers
    .map((layer) => layer.visual_cue?.duration_ms)
    .filter((ms): ms is number => typeof ms === "number" && ms > 0);
  const base = durations.length > 0 ? Math.max(...durations) : DEFAULT_AVATAR_DONE_TIMEOUT_MS;
  return base + AVATAR_DONE_TIMEOUT_GRACE_MS;
}

/**
 * Await the in-flight clip. When pauseNarrator is true (text already at next
 * anchor), TTS holds until Done — otherwise used only to serialize the next OSC.
 */
async function waitForPendingAvatarDone(
  shouldAbort: () => boolean,
  pauseNarrator: boolean
): Promise<void> {
  const pending = pendingAvatarDone;
  if (!pending) return;
  if (!pauseNarrator) {
    await pending.finished;
    return;
  }
  setPlaybackPaused(true);
  try {
    const result = await pending.finished;
    if (result?.status === "timeout") {
      console.warn(
        "[avatar] done-gate timeout — continuing narrator",
        pending.cueNames,
        result.missing.length ? `missing=${result.missing.join(",")}` : ""
      );
    }
  } catch (err) {
    if (!(err instanceof DOMException && err.name === "AbortError")) {
      console.warn("[avatar] done-gate wait failed — continuing narrator:", err);
    }
  } finally {
    if (!shouldAbort()) setPlaybackPaused(false);
  }
}

function noteAvatarStarted(
  cueNames: string[],
  timeoutMs: number,
  shouldAbort: () => boolean
): void {
  const names = cueNames.map((n) => n.trim()).filter(Boolean);
  if (!names.length) return;

  const token = Symbol("avatar-done");
  const finished = (async (): Promise<AvatarDoneWaitResult | null> => {
    if (!(await isAvatarDoneGateEnabled())) return null;
    try {
      return await waitForAvatarVideosDone(names, timeoutMs, shouldAbort);
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        console.warn("[avatar] done-gate wait failed:", err);
      }
      return null;
    }
  })();

  pendingAvatarDone = { cueNames: names, timeoutMs, finished, token };

  void finished.then(async (result) => {
    if (pendingAvatarDone?.token !== token) return;
    pendingAvatarDone = null;
    if (shouldAbort() || result == null) return;
    if (!(await isAvatarDoneGateEnabled())) return;
    // Video finished → start next avatar immediately (no text-anchor gap).
    await advanceAvatarChainAfterDone();
  });
}

/** Bind plan/fired callbacks so Done can chain the next CSV avatar without delay. */
export function bindAvatarChainContext(ctx: AvatarChainContext | null): void {
  avatarChainContext = ctx;
}

/** Clear in-flight done-wait (tests / abort). */
export function clearPendingAvatarDoneGate(): void {
  pendingAvatarDone = null;
}

/** Block narrator until any in-flight avatar finishes (e.g. show end). */
export async function flushPendingAvatarDoneGate(shouldAbort: () => boolean): Promise<void> {
  await waitForPendingAvatarDone(shouldAbort, true);
  if (pendingAvatarDone) pendingAvatarDone = null;
}

async function advanceAvatarChainAfterDone(): Promise<void> {
  const ctx = avatarChainContext;
  if (!ctx || ctx.shouldAbort()) return;
  await withAvatarFireLock(async () => {
    if (ctx.shouldAbort() || pendingAvatarDone) return;
    const next = nextUnfiredAvatarInSequence(
      ctx.plan,
      ctx.fired,
      ctx.sentenceCharStarts,
      ctx.scriptText
    );
    if (!next) return;
    const sent = await fireAvatarSegmentIfDue(
      next,
      ctx.anarchyLevelFor(next),
      ctx.onCommands,
      ctx.shouldAbort,
      { pauseNarratorForPending: false }
    );
    if (!sent) return;
    ctx.fired.add(avatarSegmentKey(next));
    ctx.onSegmentFired?.(next);
  });
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
  shouldAbort: () => boolean,
  options?: { pauseNarratorForPending?: boolean }
): Promise<boolean> {
  if (shouldAbort()) return false;
  // If text already reached the next anchor while the previous clip plays: pause TTS.
  // Chain-advance after Done uses pauseNarratorForPending=false (no extra gap).
  const pauseNarrator = options?.pauseNarratorForPending !== false;
  await waitForPendingAvatarDone(shouldAbort, pauseNarrator);
  if (shouldAbort()) return false;
  if (!(await waitWhilePlaybackPaused(shouldAbort))) return false;
  let anySent = false;
  const cueNames: string[] = [];
  for (const layer of segment.avatar_layers) {
    if (!layer.visual_cue) continue;
    if (shouldAbort()) return anySent;
    const result = await executeAvatarVisualCue(
      layer.visual_cue,
      anarchyLevel,
      onCommands,
      shouldAbort,
      segment.text_excerpt
    );
    anySent = anySent || result.executed;
    cueNames.push(...result.cueNames);
  }
  if (anySent) {
    noteAvatarStarted(cueNames, avatarDoneTimeoutMs(segment), shouldAbort);
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
  await waitForPendingAvatarDone(shouldAbort, true);
  if (shouldAbort()) return;
  const cueNames: string[] = [];
  let anySent = false;
  for (const visual of avatarVisualCuesForMoment(moment)) {
    if (shouldAbort()) return;
    const result = await executeAvatarVisualCue(
      visual,
      anarchyLevel,
      onCommands,
      shouldAbort,
      moment.text_excerpt
    );
    anySent = anySent || result.executed;
    cueNames.push(...result.cueNames);
  }
  if (anySent) {
    const durationMs =
      moment.avatar_layers
        ?.map((layer) => layer.visual_cue?.duration_ms)
        .filter((ms): ms is number => typeof ms === "number" && ms > 0)
        .reduce((a, b) => Math.max(a, b), 0) ||
      moment.avatar_video_cue?.duration_ms ||
      DEFAULT_AVATAR_DONE_TIMEOUT_MS;
    noteAvatarStarted(
      cueNames,
      (durationMs || DEFAULT_AVATAR_DONE_TIMEOUT_MS) + AVATAR_DONE_TIMEOUT_GRACE_MS,
      shouldAbort
    );
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
  if (segment.char_offset != null) return `offset:${segment.char_offset}:${segment.csv_sequence_index ?? 0}`;
  return `sequence:${segment.csv_sequence_index ?? 0}:${segment.start_sentence_index}:${segment.csv_cue_ids.join(",")}`;
}

function compareAvatarSegments(
  a: AvatarTextSegment,
  b: AvatarTextSegment,
  sentenceCharStarts: number[],
  scriptText?: string
): number {
  const offsetA = effectiveCharOffset(a, sentenceCharStarts, scriptText);
  const offsetB = effectiveCharOffset(b, sentenceCharStarts, scriptText);
  if (offsetA !== offsetB) return offsetA - offsetB;
  return (a.csv_sequence_index ?? 0) - (b.csv_sequence_index ?? 0);
}

export function sortedAvatarSegments(
  plan: Teil2PerformancePlan,
  sentenceCharStarts: number[],
  scriptText?: string
): AvatarTextSegment[] {
  return [...plan.avatar_segments].sort((a, b) =>
    compareAvatarSegments(a, b, sentenceCharStarts, scriptText)
  );
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

export function effectiveCharOffset(
  segment: AvatarTextSegment,
  sentenceCharStarts: number[],
  scriptText?: string
): number {
  if (segment.char_offset != null) return segment.char_offset;
  if (scriptText && segment.text_excerpt) {
    const needle = segment.text_excerpt.trim().slice(0, 48);
    if (needle.length >= 3) {
      const direct = scriptText.indexOf(needle);
      if (direct >= 0) return direct;
      const lowerHay = scriptText.toLowerCase();
      const lowerNeedle = needle.toLowerCase();
      const insensitive = lowerHay.indexOf(lowerNeedle);
      if (insensitive >= 0) return insensitive;
    }
  }
  return sentenceCharStarts[segment.start_sentence_index] ?? 0;
}

export function avatarSegmentsInSentence(
  plan: Teil2PerformancePlan,
  sentenceIndex: number,
  sentenceCharStarts: number[],
  scriptTextLength: number,
  scriptText?: string
): AvatarTextSegment[] {
  const sentenceStart = sentenceCharStarts[sentenceIndex] ?? 0;
  const sentenceEnd =
    sentenceIndex + 1 < sentenceCharStarts.length
      ? sentenceCharStarts[sentenceIndex + 1]!
      : scriptTextLength;
  return sortedAvatarSegments(plan, sentenceCharStarts, scriptText).filter((segment) => {
    const offset = effectiveCharOffset(segment, sentenceCharStarts, scriptText);
    return offset >= sentenceStart && offset < sentenceEnd;
  });
}

export function nextUnfiredAvatarSegment(
  plan: Teil2PerformancePlan,
  globalPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[],
  scriptText?: string
): AvatarTextSegment | null {
  for (const segment of sortedAvatarSegments(plan, sentenceCharStarts, scriptText)) {
    if (fired.has(avatarSegmentKey(segment))) continue;
    if (globalPos >= effectiveCharOffset(segment, sentenceCharStarts, scriptText)) {
      return segment;
    }
    return null;
  }
  return null;
}

/** Next unfired segment in CSV order — used to chain clips back-to-back after Done. */
export function nextUnfiredAvatarInSequence(
  plan: Teil2PerformancePlan,
  fired: Set<string>,
  sentenceCharStarts: number[],
  scriptText?: string
): AvatarTextSegment | null {
  for (const segment of sortedAvatarSegments(plan, sentenceCharStarts, scriptText)) {
    if (fired.has(avatarSegmentKey(segment))) continue;
    return segment;
  }
  return null;
}

/** @deprecated Prefer nextUnfiredAvatarSegment for strict CSV order. */
export function avatarSegmentsDueAtPosition(
  plan: Teil2PerformancePlan,
  globalPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[],
  scriptText?: string
): AvatarTextSegment[] {
  const next = nextUnfiredAvatarSegment(plan, globalPos, fired, sentenceCharStarts, scriptText);
  return next ? [next] : [];
}

export function scheduleAvatarSegmentsAtPosition(
  plan: Teil2PerformancePlan,
  globalPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[],
  anarchyLevelFor: (segment: AvatarTextSegment) => number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void,
  scriptText?: string
): void {
  pendingAvatarPositionFire = {
    plan,
    globalPos,
    fired,
    sentenceCharStarts,
    scriptText: scriptText ?? "",
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
      pending.onSegmentFired,
      pending.scriptText
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
  onSegmentFired?: (segment: AvatarTextSegment) => void,
  scriptText?: string
): Promise<void> {
  await withAvatarFireLock(async () => {
    const segment = nextUnfiredAvatarSegment(
      plan,
      globalPos,
      fired,
      sentenceCharStarts,
      scriptText
    );
    if (!segment || shouldAbort()) return;
    const sent = await fireAvatarSegmentIfDue(
      segment,
      anarchyLevelFor(segment),
      onCommands,
      shouldAbort
    );
    if (!sent) return;
    fired.add(avatarSegmentKey(segment));
    onSegmentFired?.(segment);
  });
}

export async function fireInitialAvatarSegments(
  plan: Teil2PerformancePlan,
  fired: Set<string>,
  sentenceCharStarts: number[],
  anarchyLevelFor: (segment: AvatarTextSegment) => number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void,
  scriptText?: string
): Promise<void> {
  await fireAvatarSegmentsAtPosition(
    plan,
    0,
    fired,
    sentenceCharStarts,
    anarchyLevelFor,
    onCommands,
    shouldAbort,
    onSegmentFired,
    scriptText
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
  onSegmentFired?: (segment: AvatarTextSegment) => void,
  scriptText?: string
): Promise<void> {
  const sentenceEnd =
    sentenceIndex + 1 < sentenceCharStarts.length
      ? sentenceCharStarts[sentenceIndex + 1]!
      : scriptTextLength;
  await withAvatarFireLock(async () => {
    let segment = nextUnfiredAvatarSegment(
      plan,
      sentenceEnd,
      fired,
      sentenceCharStarts,
      scriptText
    );
    while (segment) {
      const offset = effectiveCharOffset(segment, sentenceCharStarts, scriptText);
      if (offset >= sentenceEnd) break;
      if (shouldAbort()) return;
      const sent = await fireAvatarSegmentIfDue(segment, anarchyLevel, onCommands, shouldAbort);
      if (!sent) break;
      fired.add(avatarSegmentKey(segment));
      onSegmentFired?.(segment);
      segment = nextUnfiredAvatarSegment(
        plan,
        sentenceEnd,
        fired,
        sentenceCharStarts,
        scriptText
      );
    }
  });
}

export function countUnfiredAvatarSegments(
  plan: Teil2PerformancePlan,
  fired: Set<string>
): number {
  return plan.avatar_segments.filter((segment) => !fired.has(avatarSegmentKey(segment))).length;
}

/** Mark segments before a seek position as already fired so jump-in does not catch up OSC. */
export function markAvatarSegmentsBeforeAsFired(
  plan: Teil2PerformancePlan,
  beforeCharPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[],
  scriptText?: string
): number {
  let marked = 0;
  for (const segment of plan.avatar_segments) {
    const key = avatarSegmentKey(segment);
    if (fired.has(key)) continue;
    const offset = effectiveCharOffset(segment, sentenceCharStarts, scriptText);
    if (offset < beforeCharPos) {
      fired.add(key);
      marked += 1;
    }
  }
  return marked;
}
