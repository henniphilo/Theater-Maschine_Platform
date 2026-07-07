import type { CuePoint, DramaturgyDecision, OscCommand } from "@/lib/types/director";
import { fetchDirectorStatus, isDirectorPerformanceAborted, postDirectorExecute } from "@/lib/api/director";
import { sleepWallMs } from "@/lib/api/client";
import { splitSentences } from "@/lib/text/splitSentences";

let cueExecuteTail: Promise<unknown> = Promise.resolve();

function enqueueCueExecute<T>(work: () => Promise<T>): Promise<T> {
  const run = cueExecuteTail.then(work, work);
  cueExecuteTail = run.then(
    () => undefined,
    () => undefined
  );
  return run;
}

function logCueResult(
  label: string,
  decision: DramaturgyDecision,
  executed: boolean,
  blockedReason: string | null | undefined
): void {
  if (executed) return;
  const parts = [
    label,
    decision.reason,
    blockedReason ? `blocked=${blockedReason}` : "executed=false"
  ];
  console.warn("[cue]", parts.filter(Boolean).join(" — "));
}

/** Execute cues without aborting playback when the director/OSC path fails. */
export async function executeCueSafely(
  decision: DramaturgyDecision,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<boolean> {
  return enqueueCueExecute(async () => {
    if (shouldAbort() || isDirectorPerformanceAborted()) return false;
    try {
      const result = await postDirectorExecute(decision, { force: true, stagger: true });
      if (shouldAbort() || isDirectorPerformanceAborted()) return false;
      logCueResult("dramaturgy", decision, result.executed, result.blocked_reason);
      if (result.osc_commands.length > 0) {
        void onCommands(result.osc_commands).catch((err) => {
          console.warn("Cue highlight failed (playback continues):", err);
        });
      }
      return result.executed;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return false;
      console.warn("Cue execute failed (playback continues):", err);
      return false;
    }
  });
}

export function normalizeCuePoints(dramaturgy: DramaturgyDecision): CuePoint[] {
  if (dramaturgy.cue_points?.length) {
    return dramaturgy.cue_points;
  }
  if (dramaturgy.visual || dramaturgy.sound || dramaturgy.light) {
    return [
      {
        trigger: "start",
        time_offset_sec: 0,
        function: "verstärken",
        intensity: dramaturgy.intensity,
        visual: dramaturgy.visual ?? null,
        sound: dramaturgy.sound ?? null,
        light: dramaturgy.light ?? null
      }
    ];
  }
  return [];
}

export function decisionFromCuePoint(
  base: DramaturgyDecision,
  point: CuePoint
): DramaturgyDecision {
  const reason = point.function ? `[${point.function}] ${base.reason}`.trim() : base.reason;
  return {
    ...base,
    visual: point.visual ?? null,
    sound: point.sound ?? null,
    light: point.light ?? null,
    intensity: point.intensity ?? base.intensity,
    reason,
    cue_points: []
  };
}

export type CuePlaybackContext = {
  dramaturgy: DramaturgyDecision;
  beatText: string;
  fired: Set<string>;
  onCommands: (commands: OscCommand[]) => Promise<void>;
  shouldAbort: () => boolean;
};

function cueKey(point: CuePoint, suffix = ""): string {
  return `${point.trigger}:${point.keyword ?? ""}:${point.sentence_index ?? ""}:${point.time_offset_sec}${suffix}`;
}

export function fireCuePoint(ctx: CuePlaybackContext, point: CuePoint): void {
  const key = cueKey(point);
  if (ctx.fired.has(key) || ctx.shouldAbort()) return;
  ctx.fired.add(key);
  const decision = decisionFromCuePoint(ctx.dramaturgy, point);
  void executeCueSafely(decision, ctx.onCommands, ctx.shouldAbort);
}

export function fireStartCues(ctx: CuePlaybackContext): void {
  const starts = normalizeCuePoints(ctx.dramaturgy).filter((p) => p.trigger === "start");
  for (const point of starts) {
    fireCuePoint(ctx, point);
  }
}

export function fireTimeCues(ctx: CuePlaybackContext, currentTime: number): void {
  const timed = normalizeCuePoints(ctx.dramaturgy).filter(
    (p) => p.trigger === "time" && (p.time_offset_sec ?? 0) <= currentTime
  );
  for (const point of timed) {
    fireCuePoint(ctx, point);
  }
}

export function fireSentenceCues(
  ctx: CuePlaybackContext,
  sentenceIndex: number,
  sentenceText: string
): void {
  const points = normalizeCuePoints(ctx.dramaturgy);
  const sentencePoints = points.filter(
    (p) =>
      p.trigger === "sentence_end" &&
      (p.sentence_index === undefined || p.sentence_index === sentenceIndex)
  );
  for (const point of sentencePoints) {
    fireCuePoint(ctx, point);
  }

  const keywordPoints = points.filter((p) => p.trigger === "keyword" && p.keyword);
  for (const point of keywordPoints) {
    if (point.keyword && sentenceText.toLowerCase().includes(point.keyword.toLowerCase())) {
      fireCuePoint(ctx, point);
    }
  }
}

export function createCuePlaybackContext(
  dramaturgy: DramaturgyDecision,
  beatText: string,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): CuePlaybackContext {
  return {
    dramaturgy,
    beatText,
    fired: new Set(),
    onCommands,
    shouldAbort
  };
}

export function sentencesForBeat(text: string): string[] {
  return splitSentences(text);
}

export function neutralResetDecision(): DramaturgyDecision {
  return {
    visual: { action: "fade_to_black", fade_time: 2, opacity: 0 },
    sound: { action: "trigger_cue", cue_id: "alle_sounds_cut", volume: 0 },
    light: { action: "fade_blackout", fade_time: 2 },
    reason: "Neutrale Ausgangslage vor Stücktext",
    tags: [],
    mood: "neutral",
    intensity: 0,
    timestamp: 0,
    cue_points: []
  };
}

export function fireNeutralReset(
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): void {
  void executeCueSafely(neutralResetDecision(), onCommands, shouldAbort);
}

const SOUND_FADE_SUFFIXES = ["_fade_out", "_fade_in", "_out"] as const;

function soundFamilyFromCueId(cueId: string): string {
  for (const suffix of SOUND_FADE_SUFFIXES) {
    if (cueId.endsWith(suffix)) {
      return cueId.slice(0, -suffix.length);
    }
  }
  return cueId;
}

/** Fade out all active sound beds, wait, then hard-cut remaining audio. */
export async function firePerformanceEndCues(
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  options?: { fadeMs?: number }
): Promise<void> {
  if (shouldAbort() || isDirectorPerformanceAborted()) return;

  let activeCues: string[] = [];
  try {
    const status = await fetchDirectorStatus();
    activeCues = status.active_cues ?? [];
  } catch (err) {
    console.warn("Performance end: could not read active cues", err);
  }

  const fadeFamilies = new Set<string>();
  for (const cueId of activeCues) {
    if (cueId === "alle_sounds_cut") continue;
    const family = soundFamilyFromCueId(cueId);
    if (family === "alle_sounds") continue;
    fadeFamilies.add(family);
  }

  const fadeDecision = (family: string): DramaturgyDecision => ({
    sound: { action: "trigger_cue", cue_id: `${family}_fade_out`, volume: 0 },
    reason: "Aufführungsende — Sounds ausblenden",
    tags: ["teil2", "ende", "fade_out"],
    mood: "collapse",
    intensity: 0,
    timestamp: Date.now(),
    cue_points: []
  });

  await Promise.all(
    [...fadeFamilies].map((family) =>
      executeCueSafely(fadeDecision(family), onCommands, shouldAbort)
    )
  );

  const fadeMs = options?.fadeMs ?? 3000;
  if (!(await sleepWallMs(fadeMs, shouldAbort))) return;

  await executeCueSafely(
    {
      sound: { action: "trigger_cue", cue_id: "alle_sounds_cut", volume: 0 },
      reason: "Aufführungsende — Sounds Cut",
      tags: ["teil2", "ende", "cut_all"],
      mood: "collapse",
      intensity: 0,
      timestamp: Date.now(),
      cue_points: []
    },
    onCommands,
    shouldAbort
  );
}
