import type { ScriptBeat } from "@/lib/types/script";

const BAERENKLAU_RE = /bärenklau|baerenklau|bärenklauer|baerenklauer/i;

export function isBaerenklauBeat(beat: ScriptBeat): boolean {
  const haystack = `${beat.scene_title ?? ""} ${beat.text.slice(0, 400)}`;
  return BAERENKLAU_RE.test(haystack);
}

export function findBaerenklauBeats(beats: ScriptBeat[]): ScriptBeat[] {
  return beats.filter(isBaerenklauBeat);
}

export function part1Beats(beats: ScriptBeat[]): ScriptBeat[] {
  return beats;
}

export function isPart1Beat(beat: ScriptBeat, beats: ScriptBeat[]): boolean {
  const part1 = part1Beats(beats);
  return part1.some((b) => b.id === beat.id);
}
