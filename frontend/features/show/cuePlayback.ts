import type { CuePoint, DramaturgyDecision, OscCommand } from "@/lib/types/director";
import { isDirectorPerformanceAborted, postDirectorExecute } from "@/lib/api/director";
import { splitSentences } from "@/lib/text/splitSentences";

/** Execute cues without aborting playback when the director/OSC path fails. */
export async function executeCueSafely(
  decision: DramaturgyDecision,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<boolean> {
  if (shouldAbort() || isDirectorPerformanceAborted()) return false;
  try {
    const result = await postDirectorExecute(decision, { force: true, stagger: true });
    if (shouldAbort() || isDirectorPerformanceAborted()) return false;
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
