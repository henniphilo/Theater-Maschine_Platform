import type { CuePoint, DramaturgyDecision } from "@/lib/types/director";
import { postDirectorExecute } from "@/lib/api/director";
import type { OscCommand } from "@/lib/types/director";
import { splitSentences } from "@/lib/text/splitSentences";

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

export async function fireCuePoint(ctx: CuePlaybackContext, point: CuePoint): Promise<void> {
  const key = cueKey(point);
  if (ctx.fired.has(key) || ctx.shouldAbort()) return;
  ctx.fired.add(key);
  const decision = decisionFromCuePoint(ctx.dramaturgy, point);
  const result = await postDirectorExecute(decision, { force: true, stagger: true });
  if (!ctx.shouldAbort()) {
    await ctx.onCommands(result.osc_commands);
  }
}

export async function fireStartCues(ctx: CuePlaybackContext): Promise<void> {
  const starts = normalizeCuePoints(ctx.dramaturgy).filter((p) => p.trigger === "start");
  for (const point of starts) {
    await fireCuePoint(ctx, point);
  }
}

export async function fireTimeCues(ctx: CuePlaybackContext, currentTime: number): Promise<void> {
  const timed = normalizeCuePoints(ctx.dramaturgy).filter(
    (p) => p.trigger === "time" && (p.time_offset_sec ?? 0) <= currentTime
  );
  for (const point of timed) {
    await fireCuePoint(ctx, point);
  }
}

export async function fireSentenceCues(
  ctx: CuePlaybackContext,
  sentenceIndex: number,
  sentenceText: string
): Promise<void> {
  const points = normalizeCuePoints(ctx.dramaturgy);
  const sentencePoints = points.filter(
    (p) =>
      p.trigger === "sentence_end" &&
      (p.sentence_index === undefined || p.sentence_index === sentenceIndex)
  );
  for (const point of sentencePoints) {
    await fireCuePoint(ctx, point);
  }

  const keywordPoints = points.filter((p) => p.trigger === "keyword" && p.keyword);
  for (const point of keywordPoints) {
    if (point.keyword && sentenceText.toLowerCase().includes(point.keyword.toLowerCase())) {
      await fireCuePoint(ctx, point);
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
