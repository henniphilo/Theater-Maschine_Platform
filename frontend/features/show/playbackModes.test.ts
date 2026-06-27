import { describe, expect, it, vi } from "vitest";
import type { ScriptBeat } from "@/lib/types/script";

vi.mock("@/lib/api/client", () => ({
  playBlob: vi.fn().mockResolvedValue(undefined),
  setPlaybackPaused: vi.fn(),
  stopPlayback: vi.fn(),
  waitWhilePlaybackPaused: vi.fn().mockResolvedValue(true)
}));

vi.mock("@/lib/tts/prefetch", () => ({
  getCachedSpeech: vi.fn(),
  prefetchSpeech: vi.fn()
}));

vi.mock("@/features/show/cuePlayback", () => ({
  createCuePlaybackContext: vi.fn(() => ({})),
  fireSentenceCues: vi.fn(),
  fireStartCues: vi.fn(),
  fireTimeCues: vi.fn(),
  sentencesForBeat: vi.fn(() => ["Satz eins."])
}));

vi.mock("@/features/show/discussionCuePlayback", () => ({
  createDiscussionCueContext: vi.fn(() => ({
    lastSignature: null,
    onCommands: vi.fn(),
    shouldAbort: () => false
  })),
  fireDiscussionMentionsAtPosition: vi.fn().mockResolvedValue(undefined),
  scheduleDiscussionCue: vi.fn(),
  textPositionForPlayback: vi.fn(() => 0)
}));

import { runPart1ScriptPlayback } from "@/features/show/scriptPlayback";

function beatWithDiscussion(): ScriptBeat {
  return {
    id: "b1",
    order: 0,
    text: "Der Text.",
    speaker: "AI_A",
    dramaturgy: {
      reason: "test",
      tags: [],
      mood: "neutral",
      intensity: 0.5,
      timestamp: 0,
      cue_points: [
        {
          trigger: "start",
          function: "test",
          intensity: 0.5,
          sound: { action: "trigger_cue", cue_id: "maschinen_grundader", volume: 0.5 }
        }
      ]
    },
    discussion_turns: [
      {
        speaker: "anthropic",
        content: "Beim Stichwort «Text»: kalt (Sound).",
        media_mentions: []
      }
    ]
  };
}

describe("playbackModes", () => {
  it("discussion mode skips performance phase", async () => {
    const states: Array<{ segmentPhase?: string }> = [];
    await runPart1ScriptPlayback(
      [beatWithDiscussion()],
      { ttsAvailable: false },
      0,
      (update) => states.push(update),
      () => false,
      "Test",
      null,
      "discussion"
    );
    expect(states.some((s) => s.segmentPhase === "discussion")).toBe(true);
    expect(states.some((s) => s.segmentPhase === "performance")).toBe(false);
  });

  it("performance mode skips discussion phase", async () => {
    const states: Array<{ segmentPhase?: string }> = [];
    await runPart1ScriptPlayback(
      [beatWithDiscussion()],
      { ttsAvailable: false },
      0,
      (update) => states.push(update),
      () => false,
      "Test",
      null,
      "performance"
    );
    expect(states.some((s) => s.segmentPhase === "discussion")).toBe(false);
    expect(states.some((s) => s.segmentPhase === "performance")).toBe(true);
  });
});
