import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  avatarSegmentKey,
  avatarSegmentsDueAtPosition,
  avatarSegmentsInSentence,
  clearPendingAvatarDoneGate,
  bindAvatarChainContext,
  effectiveCharOffset,
  fireAvatarSegmentIfDue,
  fireRemainingSentenceSegments,
  flushPendingAvatarDoneGate,
  nextUnfiredAvatarSegment,
  resolveSentenceCharStarts,
  sentenceSpanLength,
  sortedAvatarSegments
} from "@/features/inszenierung/avatarCuePlayback";
import type { Teil2PerformancePlan } from "@/lib/types/inszenierung";

vi.mock("@/lib/api/director", () => ({
  isDirectorPerformanceAborted: () => false,
  isAvatarDoneGateEnabled: vi.fn().mockResolvedValue(false),
  waitForAvatarVideosDone: vi.fn().mockResolvedValue(null),
  postDirectorExecuteLayered: vi.fn().mockResolvedValue({
    executed: true,
    osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.Test"] }]
  })
}));

vi.mock("@/lib/api/client", () => ({
  waitWhilePlaybackPaused: vi.fn().mockResolvedValue(true),
  setPlaybackPaused: vi.fn()
}));

beforeEach(() => {
  clearPendingAvatarDoneGate();
  bindAvatarChainContext(null);
  vi.clearAllMocks();
});

describe("avatarCuePlayback position helpers", () => {
  const plan: Teil2PerformancePlan = {
    performance_speaker: "narrator",
    sentences: ["Alpha.", "Beta gamma delta."],
    sentence_char_starts: [0, 7],
    avatar_segments: [
      {
        csv_cue_ids: ["a"],
        text_excerpt: "gamma",
        char_offset: 12,
        csv_sequence_index: 0,
        start_sentence_index: 1,
        end_sentence_index: 1,
        avatar_layers: []
      }
    ],
    dramaturgy: { reason: "t", tags: [], mood: "tension", intensity: 0.5, cue_points: [] },
    anarchy_level_end: 1,
    alignment_warnings: []
  };

  it("resolves sentence char starts from plan", () => {
    expect(resolveSentenceCharStarts(plan, "Alpha. Beta gamma delta.")).toEqual([0, 7]);
  });

  it("returns segments due only after global position reaches char_offset", () => {
    const fired = new Set<string>();
    const starts = plan.sentence_char_starts!;
    expect(avatarSegmentsDueAtPosition(plan, 10, fired, starts)).toHaveLength(0);
    const due = avatarSegmentsDueAtPosition(plan, 12, fired, starts);
    expect(due).toHaveLength(1);
    expect(avatarSegmentKey(due[0])).toBe("offset:12:0");
    expect(effectiveCharOffset(due[0], starts)).toBe(12);
  });

  it("uses script span length between sentence starts", () => {
    const starts = [0, 7, 20];
    expect(sentenceSpanLength(0, starts, 30)).toBe(7);
    expect(sentenceSpanLength(1, starts, 30)).toBe(13);
    expect(sentenceSpanLength(2, starts, 30)).toBe(10);
  });

  it("filters avatar segments by char offset within sentence span", () => {
    const multi: Teil2PerformancePlan = {
      ...plan,
      sentence_char_starts: [0, 7, 20],
      avatar_segments: [
        {
          csv_cue_ids: ["a"],
          text_excerpt: "start",
          char_offset: 0,
          csv_sequence_index: 0,
          start_sentence_index: 0,
          end_sentence_index: 0,
          avatar_layers: []
        },
        {
          csv_cue_ids: ["b"],
          text_excerpt: "mid",
          char_offset: 5,
          csv_sequence_index: 1,
          start_sentence_index: 0,
          end_sentence_index: 0,
          avatar_layers: []
        },
        {
          csv_cue_ids: ["c"],
          text_excerpt: "next",
          char_offset: 7,
          csv_sequence_index: 2,
          start_sentence_index: 1,
          end_sentence_index: 1,
          avatar_layers: []
        }
      ]
    };
    const inSentence0 = avatarSegmentsInSentence(multi, 0, multi.sentence_char_starts!, 30);
    expect(inSentence0.map((s) => avatarSegmentKey(s))).toEqual(["offset:0:0", "offset:5:1"]);
    expect(avatarSegmentsInSentence(multi, 1, multi.sentence_char_starts!, 30)).toHaveLength(1);
  });

  it("fires all unfired avatar segments in a sentence", async () => {
    const multi: Teil2PerformancePlan = {
      ...plan,
      avatar_segments: [
        {
          csv_cue_ids: ["a"],
          text_excerpt: "one",
          char_offset: 0,
          csv_sequence_index: 0,
          start_sentence_index: 0,
          end_sentence_index: 0,
          avatar_layers: [{ avatar_speech_id: "a", avatar: "x", video_clip_id: "clip_a", visual_cue: { clip_id: "clip_a", video_type: "avatar", projector: "adam" } }]
        },
        {
          csv_cue_ids: ["b"],
          text_excerpt: "two",
          char_offset: 5,
          csv_sequence_index: 1,
          start_sentence_index: 0,
          end_sentence_index: 0,
          avatar_layers: [{ avatar_speech_id: "b", avatar: "x", video_clip_id: "clip_b", visual_cue: { clip_id: "clip_b", video_type: "avatar", projector: "eva" } }]
        }
      ]
    };
    const fired = new Set<string>();
    const onCommands = vi.fn().mockResolvedValue(undefined);
    await fireRemainingSentenceSegments(
      multi,
      0,
      fired,
      [0, 7],
      30,
      0.5,
      onCommands,
      () => false
    );
    expect(fired).toEqual(new Set(["offset:0:0", "offset:5:1"]));
    expect(onCommands).toHaveBeenCalledTimes(2);
  });

  it("fires only the next CSV segment in strict order", () => {
    const ordered: Teil2PerformancePlan = {
      ...plan,
      avatar_segments: [
        {
          csv_cue_ids: ["first"],
          text_excerpt: "Alpha.",
          char_offset: 12,
          csv_sequence_index: 0,
          start_sentence_index: 1,
          end_sentence_index: 1,
          avatar_layers: []
        },
        {
          csv_cue_ids: ["second"],
          text_excerpt: "gamma",
          char_offset: 12,
          csv_sequence_index: 1,
          start_sentence_index: 0,
          end_sentence_index: 0,
          avatar_layers: []
        }
      ]
    };
    const fired = new Set<string>();
    const starts = ordered.sentence_char_starts!;
    expect(nextUnfiredAvatarSegment(ordered, 20, fired, starts)).toMatchObject({
      csv_cue_ids: ["first"]
    });
    fired.add(avatarSegmentKey(ordered.avatar_segments[0]!));
    expect(nextUnfiredAvatarSegment(ordered, 20, fired, starts)).toMatchObject({
      csv_cue_ids: ["second"]
    });
    expect(nextUnfiredAvatarSegment(ordered, 10, fired, starts)).toBeNull();
    expect(sortedAvatarSegments(ordered, starts).map((s) => s.csv_cue_ids[0])).toEqual([
      "first",
      "second"
    ]);
  });
});

describe("avatar done gate", () => {
  it("keeps narrator running after avatar start (parallel)", async () => {
    const { isAvatarDoneGateEnabled, waitForAvatarVideosDone } = await import("@/lib/api/director");
    const { setPlaybackPaused } = await import("@/lib/api/client");

    vi.mocked(isAvatarDoneGateEnabled).mockResolvedValue(true);
    vi.mocked(waitForAvatarVideosDone).mockResolvedValue({
      status: "done",
      received: ["KI_RZ21.Test"],
      missing: [],
      wait_ms: 10
    });

    const segment = {
      csv_cue_ids: ["a"],
      text_excerpt: "Alpha.",
      char_offset: 0,
      csv_sequence_index: 0,
      start_sentence_index: 0,
      end_sentence_index: 0,
      avatar_layers: [
        {
          avatar_speech_id: "a",
          avatar: "delfin",
          video_clip_id: "test",
          visual_cue: {
            action: "play_clip",
            clip_id: "test",
            video_type: "avatar" as const,
            duration_ms: 1000
          }
        }
      ]
    };

    const ok = await fireAvatarSegmentIfDue(segment, 0.5, async () => undefined, () => false);
    expect(ok).toBe(true);
    // Done-wait arms in background without pausing TTS.
    expect(setPlaybackPaused).not.toHaveBeenCalled();
    await vi.waitFor(() => {
      expect(waitForAvatarVideosDone).toHaveBeenCalled();
    });
  });

  it("serializes avatars without pausing narrator when previous still pending", async () => {
    const { isAvatarDoneGateEnabled, waitForAvatarVideosDone, postDirectorExecuteLayered } =
      await import("@/lib/api/director");
    const { setPlaybackPaused } = await import("@/lib/api/client");

    let resolveDone: (value: {
      status: "done";
      received: string[];
      missing: string[];
      wait_ms: number;
    }) => void = () => undefined;
    const donePromise = new Promise<{
      status: "done";
      received: string[];
      missing: string[];
      wait_ms: number;
    }>((resolve) => {
      resolveDone = resolve;
    });

    vi.mocked(isAvatarDoneGateEnabled).mockResolvedValue(true);
    vi.mocked(waitForAvatarVideosDone)
      .mockImplementationOnce(() => donePromise)
      .mockResolvedValue({
        status: "done",
        received: ["KI_RZ21.Second"],
        missing: [],
        wait_ms: 1
      });
    vi.mocked(postDirectorExecuteLayered)
      .mockResolvedValueOnce({
        executed: true,
        osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.First"] }]
      })
      .mockResolvedValueOnce({
        executed: true,
        osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.Second"] }]
      });

    const layer = (clip: string) => ({
      avatar_speech_id: clip,
      avatar: "delfin",
      video_clip_id: clip,
      visual_cue: {
        action: "play_clip" as const,
        clip_id: clip,
        video_type: "avatar" as const,
        duration_ms: 1000
      }
    });

    const first = {
      csv_cue_ids: ["a"],
      text_excerpt: "Alpha.",
      char_offset: 0,
      csv_sequence_index: 0,
      start_sentence_index: 0,
      end_sentence_index: 0,
      avatar_layers: [layer("first")]
    };
    const second = {
      csv_cue_ids: ["b"],
      text_excerpt: "Beta.",
      char_offset: 10,
      csv_sequence_index: 1,
      start_sentence_index: 1,
      end_sentence_index: 1,
      avatar_layers: [layer("second")]
    };

    await fireAvatarSegmentIfDue(first, 0.5, async () => undefined, () => false);
    expect(setPlaybackPaused).not.toHaveBeenCalled();

    const secondFire = fireAvatarSegmentIfDue(second, 0.5, async () => undefined, () => false);
    await vi.waitFor(() => {
      expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(1);
    });
    resolveDone({
      status: "done",
      received: ["KI_RZ21.First"],
      missing: [],
      wait_ms: 10
    });
    await secondFire;
    expect(waitForAvatarVideosDone).toHaveBeenCalled();
    expect(setPlaybackPaused).not.toHaveBeenCalled();
  });

  it("flushPendingAvatarDoneGate waits for in-flight clip at show end", async () => {
    const { isAvatarDoneGateEnabled, waitForAvatarVideosDone } = await import("@/lib/api/director");
    const { setPlaybackPaused } = await import("@/lib/api/client");

    vi.mocked(isAvatarDoneGateEnabled).mockResolvedValue(true);
    vi.mocked(waitForAvatarVideosDone).mockResolvedValue({
      status: "done",
      received: ["KI_RZ21.Test"],
      missing: [],
      wait_ms: 5
    });

    await fireAvatarSegmentIfDue(
      {
        csv_cue_ids: ["a"],
        text_excerpt: "Alpha.",
        char_offset: 0,
        csv_sequence_index: 0,
        start_sentence_index: 0,
        end_sentence_index: 0,
        avatar_layers: [
          {
            avatar_speech_id: "a",
            avatar: "delfin",
            video_clip_id: "test",
            visual_cue: {
              action: "play_clip",
              clip_id: "test",
              video_type: "avatar",
              duration_ms: 1000
            }
          }
        ]
      },
      0.5,
      async () => undefined,
      () => false
    );
    // Background wait starts immediately (parallel); flush also awaits it.
    await flushPendingAvatarDoneGate(() => false);
    expect(waitForAvatarVideosDone).toHaveBeenCalled();
    expect(setPlaybackPaused).toHaveBeenCalledWith(true);
    expect(setPlaybackPaused).toHaveBeenCalledWith(false);
  });

  it("chains the next avatar immediately when previous Done arrives", async () => {
    const { isAvatarDoneGateEnabled, waitForAvatarVideosDone, postDirectorExecuteLayered } =
      await import("@/lib/api/director");
    const { setPlaybackPaused } = await import("@/lib/api/client");
    const { bindAvatarChainContext, avatarSegmentKey } = await import(
      "@/features/inszenierung/avatarCuePlayback"
    );

    let resolveDone: (value: {
      status: "done";
      received: string[];
      missing: string[];
      wait_ms: number;
    }) => void = () => undefined;
    const donePromise = new Promise<{
      status: "done";
      received: string[];
      missing: string[];
      wait_ms: number;
    }>((resolve) => {
      resolveDone = resolve;
    });

    vi.mocked(isAvatarDoneGateEnabled).mockResolvedValue(true);
    vi.mocked(waitForAvatarVideosDone)
      .mockImplementationOnce(() => donePromise)
      .mockResolvedValue({
        status: "done",
        received: ["KI_RZ21.Second"],
        missing: [],
        wait_ms: 1
      });
    vi.mocked(postDirectorExecuteLayered)
      .mockResolvedValueOnce({
        executed: true,
        osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.First"] }]
      })
      .mockResolvedValueOnce({
        executed: true,
        osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.Second"] }]
      });

    const layer = (clip: string) => ({
      avatar_speech_id: clip,
      avatar: "delfin",
      video_clip_id: clip,
      visual_cue: {
        action: "play_clip" as const,
        clip_id: clip,
        video_type: "avatar" as const,
        duration_ms: 1000
      }
    });

    const first = {
      csv_cue_ids: ["a"],
      text_excerpt: "Alpha.",
      char_offset: 0,
      csv_sequence_index: 0,
      start_sentence_index: 0,
      end_sentence_index: 0,
      avatar_layers: [layer("first")]
    };
    const second = {
      csv_cue_ids: ["b"],
      text_excerpt: "Beta.",
      char_offset: 500,
      csv_sequence_index: 1,
      start_sentence_index: 1,
      end_sentence_index: 1,
      avatar_layers: [layer("second")]
    };

    const plan = {
      performance_speaker: "narrator" as const,
      sentences: ["Alpha.", "Beta."],
      sentence_char_starts: [0, 7],
      avatar_segments: [first, second],
      dramaturgy: { reason: "t", tags: [], mood: "tension" as const, intensity: 0.5, cue_points: [] },
      anarchy_level_end: 1,
      alignment_warnings: []
    };
    const fired = new Set<string>();
    const firedOrder: string[] = [];

    bindAvatarChainContext({
      plan,
      fired,
      sentenceCharStarts: plan.sentence_char_starts,
      scriptText: "Alpha. Beta.",
      anarchyLevelFor: () => 0.5,
      onCommands: async () => undefined,
      shouldAbort: () => false,
      onSegmentFired: (segment) => {
        firedOrder.push(avatarSegmentKey(segment));
      }
    });

    await fireAvatarSegmentIfDue(first, 0.5, async () => undefined, () => false);
    fired.add(avatarSegmentKey(first));
    expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(1);
    expect(setPlaybackPaused).not.toHaveBeenCalled();

    // Done arrives while narrator is still far from second char_offset (500).
    resolveDone({
      status: "done",
      received: ["KI_RZ21.First"],
      missing: [],
      wait_ms: 1
    });
    await vi.waitFor(() => {
      expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(2);
    });
    expect(fired.has(avatarSegmentKey(second))).toBe(true);
    expect(setPlaybackPaused).not.toHaveBeenCalled();

    bindAvatarChainContext(null);
  });

  it("chains the next avatar on CSV duration even if Done-gate status fetch hangs", async () => {
    vi.useFakeTimers();
    const { isAvatarDoneGateEnabled, postDirectorExecuteLayered } = await import("@/lib/api/director");
    const {
      fireAvatarSegmentIfDue,
      bindAvatarChainContext,
      avatarSegmentKey,
      resetAvatarPlaybackState
    } = await import("@/features/inszenierung/avatarCuePlayback");

    // Never resolves — previously this prevented arming the duration timer.
    vi.mocked(isAvatarDoneGateEnabled).mockImplementation(() => new Promise(() => undefined));
    vi.mocked(postDirectorExecuteLayered)
      .mockResolvedValueOnce({
        executed: true,
        osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.First"] }]
      })
      .mockResolvedValueOnce({
        executed: true,
        osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.Second"] }]
      });

    const layer = (clip: string, durationMs: number) => ({
      avatar_speech_id: clip,
      avatar: "delfin",
      video_clip_id: clip,
      visual_cue: {
        action: "play_clip" as const,
        clip_id: clip,
        video_type: "avatar" as const,
        duration_ms: durationMs
      }
    });

    const first = {
      csv_cue_ids: ["a"],
      text_excerpt: "Alpha.",
      char_offset: 0,
      csv_sequence_index: 0,
      start_sentence_index: 0,
      end_sentence_index: 0,
      avatar_layers: [layer("first", 1_000)]
    };
    const second = {
      csv_cue_ids: ["b"],
      text_excerpt: "Beta.",
      char_offset: 500,
      csv_sequence_index: 1,
      start_sentence_index: 1,
      end_sentence_index: 1,
      avatar_layers: [layer("second", 1_000)]
    };

    const plan = {
      performance_speaker: "narrator" as const,
      sentences: ["Alpha.", "Beta."],
      sentence_char_starts: [0, 7],
      avatar_segments: [first, second],
      dramaturgy: { reason: "t", tags: [], mood: "tension" as const, intensity: 0.5, cue_points: [] },
      anarchy_level_end: 1,
      alignment_warnings: []
    };
    const fired = new Set<string>([avatarSegmentKey(first)]);

    bindAvatarChainContext({
      plan,
      fired,
      sentenceCharStarts: plan.sentence_char_starts,
      scriptText: "Alpha. Beta.",
      anarchyLevelFor: () => 0.5,
      onCommands: async () => undefined,
      shouldAbort: () => false
    });

    await fireAvatarSegmentIfDue(first, 0.5, async () => undefined, () => false);
    expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1_000);
    await vi.waitFor(() => {
      expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(2);
    });
    expect(fired.has(avatarSegmentKey(second))).toBe(true);

    resetAvatarPlaybackState();
    vi.useRealTimers();
  });

  it("retries a blocked segment instead of burning later CSV avatars", async () => {
    vi.useFakeTimers();
    const { isAvatarDoneGateEnabled, postDirectorExecuteLayered } = await import("@/lib/api/director");
    const {
      fireAvatarSegmentIfDue,
      bindAvatarChainContext,
      avatarSegmentKey,
      resetAvatarPlaybackState
    } = await import("@/features/inszenierung/avatarCuePlayback");

    vi.mocked(isAvatarDoneGateEnabled).mockResolvedValue(false);
    vi.mocked(postDirectorExecuteLayered)
      .mockResolvedValueOnce({
        executed: true,
        osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.First"] }]
      })
      .mockResolvedValueOnce({
        executed: false,
        osc_commands: [],
        blocked_reason: "media_density_too_high"
      })
      .mockResolvedValueOnce({
        executed: true,
        osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.Second"] }]
      });

    const layer = (clip: string) => ({
      avatar_speech_id: clip,
      avatar: "delfin",
      video_clip_id: clip,
      visual_cue: {
        action: "play_clip" as const,
        clip_id: clip,
        video_type: "avatar" as const,
        duration_ms: 500
      }
    });

    const first = {
      csv_cue_ids: ["a"],
      text_excerpt: "Alpha.",
      char_offset: 0,
      csv_sequence_index: 0,
      start_sentence_index: 0,
      end_sentence_index: 0,
      avatar_layers: [layer("first")]
    };
    const second = {
      ...first,
      csv_cue_ids: ["b"],
      csv_sequence_index: 1,
      text_excerpt: "Beta.",
      avatar_layers: [layer("second")]
    };
    const third = {
      ...first,
      csv_cue_ids: ["c"],
      csv_sequence_index: 2,
      text_excerpt: "Gamma.",
      avatar_layers: [layer("third")]
    };

    const plan = {
      performance_speaker: "narrator" as const,
      sentences: ["Alpha.", "Beta.", "Gamma."],
      sentence_char_starts: [0, 7, 13],
      avatar_segments: [first, second, third],
      dramaturgy: { reason: "t", tags: [], mood: "tension" as const, intensity: 0.5, cue_points: [] },
      anarchy_level_end: 1,
      alignment_warnings: []
    };
    const fired = new Set<string>([avatarSegmentKey(first)]);

    bindAvatarChainContext({
      plan,
      fired,
      sentenceCharStarts: plan.sentence_char_starts,
      scriptText: "Alpha. Beta. Gamma.",
      anarchyLevelFor: () => 0.5,
      onCommands: async () => undefined,
      shouldAbort: () => false
    });

    await fireAvatarSegmentIfDue(first, 0.5, async () => undefined, () => false);
    await vi.advanceTimersByTimeAsync(500);
    // First retry attempt still blocked — second must stay unfired (not burned).
    await Promise.resolve();
    expect(fired.has(avatarSegmentKey(second))).toBe(false);
    expect(fired.has(avatarSegmentKey(third))).toBe(false);

    await vi.advanceTimersByTimeAsync(1_500);
    await vi.waitFor(() => {
      expect(fired.has(avatarSegmentKey(second))).toBe(true);
    });
    expect(fired.has(avatarSegmentKey(third))).toBe(false);
    expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(3);

    resetAvatarPlaybackState();
    vi.useRealTimers();
  });

  it("drainRemainingAvatarChain finishes CSV after narrator would have stopped", async () => {
    vi.useFakeTimers();
    const { isAvatarDoneGateEnabled, postDirectorExecuteLayered } = await import("@/lib/api/director");
    const {
      fireAvatarSegmentIfDue,
      bindAvatarChainContext,
      drainRemainingAvatarChain,
      avatarSegmentKey,
      resetAvatarPlaybackState
    } = await import("@/features/inszenierung/avatarCuePlayback");

    vi.mocked(isAvatarDoneGateEnabled).mockResolvedValue(false);
    vi.mocked(postDirectorExecuteLayered).mockImplementation(async (decision) => ({
      executed: true,
      osc_commands: [
        {
          bridge: "pixera",
          args: [`KI_RZ21.${String(decision.visual?.clip_id ?? "x")}`]
        }
      ]
    }));

    const layer = (clip: string, durationMs: number) => ({
      avatar_speech_id: clip,
      avatar: "delfin",
      video_clip_id: clip,
      visual_cue: {
        action: "play_clip" as const,
        clip_id: clip,
        video_type: "avatar" as const,
        duration_ms: durationMs
      }
    });

    const first = {
      csv_cue_ids: ["sch6"],
      text_excerpt: "Gestirne.",
      char_offset: 0,
      csv_sequence_index: 0,
      start_sentence_index: 0,
      end_sentence_index: 0,
      avatar_layers: [layer("sch6", 500)]
    };
    const second = {
      ...first,
      csv_cue_ids: ["sch7"],
      csv_sequence_index: 1,
      text_excerpt: "dramatischer.",
      avatar_layers: [layer("sch7", 800)]
    };
    const third = {
      ...first,
      csv_cue_ids: ["sch8"],
      csv_sequence_index: 2,
      text_excerpt: "Erde erben.",
      avatar_layers: [layer("sch8", 400)]
    };

    const plan = {
      performance_speaker: "narrator" as const,
      sentences: ["Gestirne.", "dramatischer.", "Erde erben."],
      sentence_char_starts: [0, 10, 24],
      avatar_segments: [first, second, third],
      dramaturgy: { reason: "t", tags: [], mood: "tension" as const, intensity: 0.5, cue_points: [] },
      anarchy_level_end: 1,
      alignment_warnings: []
    };
    const fired = new Set<string>();

    bindAvatarChainContext({
      plan,
      fired,
      sentenceCharStarts: plan.sentence_char_starts,
      scriptText: "Gestirne. dramatischer. Erde erben.",
      anarchyLevelFor: () => 0.5,
      onCommands: async () => undefined,
      shouldAbort: () => false
    });

    await fireAvatarSegmentIfDue(first, 0.5, async () => undefined, () => false);
    fired.add(avatarSegmentKey(first));

    const drain = drainRemainingAvatarChain(() => false, plan, fired);
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(800);
    await vi.advanceTimersByTimeAsync(400);
    await drain;

    expect(fired.has(avatarSegmentKey(second))).toBe(true);
    expect(fired.has(avatarSegmentKey(third))).toBe(true);
    expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(3);

    resetAvatarPlaybackState();
    vi.useRealTimers();
  });

  it("drain does not start the next CSV clip while the previous duration is still running", async () => {
    vi.useFakeTimers();
    const { isAvatarDoneGateEnabled, postDirectorExecuteLayered } = await import("@/lib/api/director");
    const {
      fireAvatarSegmentIfDue,
      bindAvatarChainContext,
      drainRemainingAvatarChain,
      avatarSegmentKey,
      resetAvatarPlaybackState
    } = await import("@/features/inszenierung/avatarCuePlayback");

    vi.mocked(isAvatarDoneGateEnabled).mockResolvedValue(false);
    const calls: string[] = [];
    vi.mocked(postDirectorExecuteLayered).mockImplementation(async (decision) => {
      const clip = String(decision.visual?.clip_id ?? "");
      calls.push(clip);
      return {
        executed: true,
        osc_commands: [{ bridge: "pixera", args: [`KI_RZ21.${clip}`] }]
      };
    });

    const layer = (clip: string, durationMs: number) => ({
      avatar_speech_id: clip,
      avatar: "delfin",
      video_clip_id: clip,
      visual_cue: {
        action: "play_clip" as const,
        clip_id: clip,
        video_type: "avatar" as const,
        duration_ms: durationMs
      }
    });

    const sch7 = {
      csv_cue_ids: ["sch7"],
      text_excerpt: "dramatischer.",
      char_offset: 0,
      csv_sequence_index: 0,
      start_sentence_index: 0,
      end_sentence_index: 0,
      avatar_layers: [layer("sch7", 5_000)]
    };
    const sch8 = {
      ...sch7,
      csv_cue_ids: ["sch8"],
      csv_sequence_index: 1,
      text_excerpt: "Erde erben.",
      avatar_layers: [layer("sch8", 1_000)]
    };

    const plan = {
      performance_speaker: "narrator" as const,
      sentences: ["dramatischer.", "Erde erben."],
      sentence_char_starts: [0, 14],
      avatar_segments: [sch7, sch8],
      dramaturgy: { reason: "t", tags: [], mood: "tension" as const, intensity: 0.5, cue_points: [] },
      anarchy_level_end: 1,
      alignment_warnings: []
    };
    const fired = new Set<string>();

    bindAvatarChainContext({
      plan,
      fired,
      sentenceCharStarts: plan.sentence_char_starts,
      scriptText: "dramatischer. Erde erben.",
      anarchyLevelFor: () => 0.5,
      onCommands: async () => undefined,
      shouldAbort: () => false
    });

    await fireAvatarSegmentIfDue(sch7, 0.5, async () => undefined, () => false);
    fired.add(avatarSegmentKey(sch7));
    expect(calls).toEqual(["sch7"]);

    const drainPromise = drainRemainingAvatarChain(() => false, plan, fired);

    // Mid-sch7: drain must not fire sch8 yet.
    await vi.advanceTimersByTimeAsync(2_000);
    expect(calls).toEqual(["sch7"]);
    expect(fired.has(avatarSegmentKey(sch8))).toBe(false);

    // Finish sch7 duration, let advance arm sch8, then finish sch8.
    await vi.advanceTimersByTimeAsync(3_000);
    await vi.advanceTimersByTimeAsync(100);
    await vi.advanceTimersByTimeAsync(1_000);
    await vi.advanceTimersByTimeAsync(2_000);
    await drainPromise;

    expect(calls).toEqual(["sch7", "sch8"]);
    expect(fired.has(avatarSegmentKey(sch8))).toBe(true);

    resetAvatarPlaybackState();
    vi.useRealTimers();
  }, 10_000);

  it("ignores delayed chain timers after resetAvatarPlaybackState (second-run safety)", async () => {
    vi.useFakeTimers();
    const { isAvatarDoneGateEnabled, postDirectorExecuteLayered } = await import("@/lib/api/director");
    const {
      fireAvatarSegmentIfDue,
      bindAvatarChainContext,
      resetAvatarPlaybackState,
      avatarSegmentKey
    } = await import("@/features/inszenierung/avatarCuePlayback");

    vi.mocked(isAvatarDoneGateEnabled).mockResolvedValue(false);
    vi.mocked(postDirectorExecuteLayered).mockResolvedValue({
      executed: true,
      osc_commands: [{ bridge: "pixera", args: ["KI_RZ21.First"] }]
    });

    const first = {
      csv_cue_ids: ["a"],
      text_excerpt: "Alpha.",
      char_offset: 0,
      csv_sequence_index: 0,
      start_sentence_index: 0,
      end_sentence_index: 0,
      avatar_layers: [
        {
          avatar_speech_id: "a",
          avatar: "delfin",
          video_clip_id: "first",
          visual_cue: {
            action: "play_clip" as const,
            clip_id: "first",
            video_type: "avatar" as const,
            duration_ms: 5_000
          }
        }
      ]
    };
    const second = {
      ...first,
      csv_cue_ids: ["b"],
      csv_sequence_index: 1,
      text_excerpt: "Beta.",
      avatar_layers: [
        {
          avatar_speech_id: "b",
          avatar: "delfin",
          video_clip_id: "second",
          visual_cue: {
            action: "play_clip" as const,
            clip_id: "second",
            video_type: "avatar" as const,
            duration_ms: 5_000
          }
        }
      ]
    };

    const fired = new Set<string>();
    const plan = {
      version: 1 as const,
      sentences: ["Alpha.", "Beta."],
      sentence_char_starts: [0, 7],
      performance_speaker: "narrator" as const,
      anarchy_level_end: 0.5,
      dramaturgy: { reason: "t", tags: [], mood: "neutral", intensity: 0.5 },
      avatar_segments: [first, second],
      atmosphere_cue_points: []
    };

    bindAvatarChainContext({
      plan,
      fired,
      sentenceCharStarts: [0, 7],
      scriptText: "Alpha. Beta.",
      anarchyLevelFor: () => 0.5,
      onCommands: async () => undefined,
      shouldAbort: () => false
    });

    await fireAvatarSegmentIfDue(first, 0.5, async () => undefined, () => false);
    fired.add(avatarSegmentKey(first));
    expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(1);

    // Simulate Stop → second Play: epoch bump must kill the CSV-duration timer.
    resetAvatarPlaybackState();
    bindAvatarChainContext({
      plan,
      fired: new Set(),
      sentenceCharStarts: [0, 7],
      scriptText: "Alpha. Beta.",
      anarchyLevelFor: () => 0.5,
      onCommands: async () => undefined,
      shouldAbort: () => false
    });

    await vi.advanceTimersByTimeAsync(6_000);
    expect(postDirectorExecuteLayered).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
