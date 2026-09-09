import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  createCuePlaybackContext,
  executeCueSafely,
  fireTimeCues,
  markTimeCuesAsFired,
  markTimeCuesBefore,
  TIME_CUE_MAX_CATCH_UP_SEC
} from "@/features/show/cuePlayback";
import type { DramaturgyDecision } from "@/lib/types/director";

vi.mock("@/lib/api/director", () => ({
  postDirectorExecute: vi.fn(),
  isDirectorPerformanceAborted: vi.fn(() => false),
  fetchDirectorStatus: vi.fn()
}));

vi.mock("@/lib/api/client", () => ({
  sleepWallMs: vi.fn().mockResolvedValue(true)
}));

import { postDirectorExecute } from "@/lib/api/director";

const decision: DramaturgyDecision = {
  sound: { action: "trigger_cue", cue_id: "maschinen_grundader" },
  reason: "test",
  tags: [],
  mood: "neutral",
  intensity: 0.5,
  timestamp: 0
};

describe("executeCueSafely", () => {
  beforeEach(() => {
    vi.mocked(postDirectorExecute).mockReset();
  });

  it("continues without throwing when director execute fails", async () => {
    vi.mocked(postDirectorExecute).mockRejectedValue(new Error("Director execute failed"));
    const onCommands = vi.fn();

    const executed = await executeCueSafely(decision, onCommands, () => false);

    expect(executed).toBe(false);
    expect(onCommands).not.toHaveBeenCalled();
  });

  it("forwards osc commands on success", async () => {
    const cmd = {
      bridge: "sound",
      host: "127.0.0.1",
      port: 9000,
      address: "/sound/trigger",
      args: ["maschinen_grundader", 0.6],
      dry_run: false
    };
    vi.mocked(postDirectorExecute).mockResolvedValue({
      executed: true,
      blocked_reason: null,
      osc_commands: [cmd]
    });
    const onCommands = vi.fn().mockResolvedValue(undefined);

    const executed = await executeCueSafely(decision, onCommands, () => false);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(executed).toBe(true);
    expect(onCommands).toHaveBeenCalledWith([cmd]);
  });

  it("does not wait for slow cue highlights", async () => {
    vi.mocked(postDirectorExecute).mockResolvedValue({
      executed: true,
      blocked_reason: null,
      osc_commands: [
        {
          bridge: "sound",
          host: "127.0.0.1",
          port: 9000,
          address: "/sound/trigger",
          args: ["test", 0.5],
          dry_run: false
        }
      ]
    });
    let highlightDone = false;
    const onCommands = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          setTimeout(() => {
            highlightDone = true;
            resolve();
          }, 200);
        })
    );

    const started = Date.now();
    await executeCueSafely(decision, onCommands, () => false);
    const elapsed = Date.now() - started;

    expect(elapsed).toBeLessThan(50);
    expect(highlightDone).toBe(false);
  });
});

describe("markTimeCuesBefore", () => {
  const dramaturgy: DramaturgyDecision = {
    reason: "cues",
    tags: [],
    mood: "neutral",
    intensity: 0.5,
    timestamp: 0,
    cue_points: [
      { trigger: "time", time_offset_sec: 2, function: "past", intensity: 0.5 },
      { trigger: "time", time_offset_sec: 10, function: "future", intensity: 0.5 },
      { trigger: "sentence_end", sentence_index: 0, time_offset_sec: 0, function: "sentence", intensity: 0.5 }
    ]
  };

  it("marks only time cues at or before the seek clock", () => {
    const ctx = createCuePlaybackContext(dramaturgy, "text", async () => undefined, () => false);
    markTimeCuesBefore(ctx, 5);
    expect(ctx.fired.size).toBe(1);
    expect([...ctx.fired][0]).toContain("2");
    expect(ctx.lastClockSec).toBe(5);
  });

  it("markTimeCuesAsFired still marks all time cues", () => {
    const ctx = createCuePlaybackContext(dramaturgy, "text", async () => undefined, () => false);
    markTimeCuesAsFired(ctx);
    expect(ctx.fired.size).toBe(2);
  });
});

describe("fireTimeCues catch-up window", () => {
  const dramaturgy: DramaturgyDecision = {
    reason: "time-cues",
    tags: [],
    mood: "neutral",
    intensity: 0.5,
    timestamp: 0,
    cue_points: [
      { trigger: "time", time_offset_sec: 5, function: "a", sound: { action: "trigger_cue", cue_id: "a" } },
      { trigger: "time", time_offset_sec: 20, function: "b", sound: { action: "trigger_cue", cue_id: "b" } },
      { trigger: "time", time_offset_sec: 40, function: "c", sound: { action: "trigger_cue", cue_id: "c" } },
      {
        trigger: "time",
        time_offset_sec: 41,
        function: "recent",
        sound: { action: "trigger_cue", cue_id: "recent" }
      }
    ]
  };

  beforeEach(() => {
    vi.mocked(postDirectorExecute).mockReset();
    vi.mocked(postDirectorExecute).mockResolvedValue({
      executed: true,
      blocked_reason: null,
      osc_commands: []
    });
  });

  it("fires gradual advances without skipping", async () => {
    const ctx = createCuePlaybackContext(dramaturgy, "text", async () => undefined, () => false);
    fireTimeCues(ctx, 5);
    fireTimeCues(ctx, 20);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(postDirectorExecute).toHaveBeenCalledTimes(2);
  });

  it("skips mid-gap cues when show clock jumps past max catch-up", async () => {
    const ctx = createCuePlaybackContext(dramaturgy, "text", async () => undefined, () => false);
    fireTimeCues(ctx, 5);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(postDirectorExecute).toHaveBeenCalledTimes(1);

    vi.mocked(postDirectorExecute).mockClear();
    // Jump ~36s — larger than TIME_CUE_MAX_CATCH_UP_SEC
    fireTimeCues(ctx, 5 + TIME_CUE_MAX_CATCH_UP_SEC + 36);
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Only the recent window near t≈41 should execute (offset 41); 20 and 40 are skipped.
    const reasons = vi.mocked(postDirectorExecute).mock.calls.map(
      (call) => (call[0] as DramaturgyDecision).reason
    );
    expect(reasons.some((r) => r?.includes("recent"))).toBe(true);
    expect(reasons.some((r) => r?.includes("[b]"))).toBe(false);
    expect(reasons.some((r) => r?.includes("[c]"))).toBe(false);
  });
});
