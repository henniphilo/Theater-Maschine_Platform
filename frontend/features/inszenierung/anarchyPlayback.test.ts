import { describe, expect, it } from "vitest";

import { computeMomentDelayMs } from "./anarchyPlayback";
import { momentSpeechLabel } from "./inszenierungBuffer";
import type { CompositionMoment } from "@/lib/types/inszenierung";

function moment(overrides: Partial<CompositionMoment> = {}): CompositionMoment {
  return {
    id: "m1",
    order: 0,
    scene_id: "s1",
    text_excerpt: "Text",
    speaker: "AI_A",
    dramaturgy: null,
    overlap_with_previous: 0,
    anarchy_level: 0.2,
    start_delay_ms: 1000,
    duration_hint_ms: 3000,
    ...overrides
  };
}

describe("anarchyPlayback scheduling", () => {
  it("shortens delay when overlap increases", () => {
    const base = moment({ start_delay_ms: 1000, overlap_with_previous: 0 });
    const overlapped = moment({ start_delay_ms: 1000, overlap_with_previous: 0.5 });
    expect(computeMomentDelayMs(base, 1)).toBe(1000);
    expect(computeMomentDelayMs(overlapped, 1)).toBe(400);
  });

  it("never returns negative delay", () => {
    const heavy = moment({ start_delay_ms: 200, overlap_with_previous: 0.9 });
    expect(computeMomentDelayMs(heavy, 1)).toBe(0);
  });
});

describe("momentSpeechLabel", () => {
  it("labels avatar and ki modes", () => {
    expect(
      momentSpeechLabel(
        moment({ speech_mode: "avatar_video", avatar_speech_id: "BK3" })
      )
    ).toBe("Avatar BK3");
    expect(momentSpeechLabel(moment({ speech_mode: "tts", speaker: "AI_B" }))).toBe("KI Stimme B");
    expect(momentSpeechLabel(moment({ speech_mode: "silent" }))).toBe("Stumm");
  });
});
