import { describe, expect, it, vi, beforeEach } from "vitest";

import { runTextSyncPlayback } from "@/features/inszenierung/teil2TextSyncPlayback";
import type { SceneCorpus, Teil2PerformancePlan } from "@/lib/types/inszenierung";

const fireInitialAvatarSegments = vi.fn().mockResolvedValue(undefined);
const countUnfiredAvatarSegments = vi.fn().mockReturnValue(0);
const scheduleAvatarSegmentsAtPosition = vi.fn();
const drainRemainingAvatarChain = vi.fn().mockResolvedValue(undefined);
const resolveSentenceSpeech = vi.fn().mockResolvedValue(new Blob(["audio"]));

vi.mock("@/features/inszenierung/avatarCuePlayback", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/inszenierung/avatarCuePlayback")>();
  return {
    ...actual,
    scheduleAvatarSegmentsAtPosition: (...args: unknown[]) => scheduleAvatarSegmentsAtPosition(...args),
    fireInitialAvatarSegments: (...args: unknown[]) => fireInitialAvatarSegments(...args),
    countUnfiredAvatarSegments: (...args: unknown[]) => countUnfiredAvatarSegments(...args),
    drainRemainingAvatarChain: (...args: unknown[]) => drainRemainingAvatarChain(...args)
  };
});

vi.mock("@/features/inszenierung/inszenierungBuffer", () => ({
  resolveSentenceSpeech: (...args: unknown[]) => resolveSentenceSpeech(...args)
}));

const playBlob = vi.fn();

vi.mock("@/lib/api/client", () => ({
  playBlob: (...args: unknown[]) => playBlob(...args),
  waitWhilePlaybackPaused: vi.fn().mockResolvedValue(true),
  sleepWallMs: vi.fn().mockResolvedValue(true),
  getPlaybackRate: vi.fn().mockReturnValue(1)
}));

vi.mock("@/lib/api/director", () => ({
  armDirectorForPerformance: vi.fn(),
  stopDirectorPerformance: vi.fn(),
  postDirectorExecute: vi.fn().mockResolvedValue({
    executed: true,
    blocked_reason: null,
    osc_commands: []
  }),
  isDirectorPerformanceAborted: () => false,
  isAvatarDoneGateEnabled: vi.fn().mockResolvedValue(false),
  waitForAvatarVideosDone: vi.fn().mockResolvedValue(null)
}));

vi.mock("@/features/show/cuePlayback", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/show/cuePlayback")>();
  return {
    ...actual,
    firePerformanceEndCues: vi.fn().mockResolvedValue(undefined)
  };
});

function basePlan(overrides: Partial<Teil2PerformancePlan>): Teil2PerformancePlan {
  return {
    performance_speaker: "narrator",
    sentences: ["Erster Satz.", "Zweiter Satz mit Avatar."],
    sentence_char_starts: [0, 13],
    avatar_segments: [
      {
        csv_cue_ids: ["BK1_Caro"],
        text_excerpt: "Zweiter Satz mit Avatar.",
        char_offset: 13,
        start_sentence_index: 1,
        end_sentence_index: 1,
        avatar_layers: []
      }
    ],
    dramaturgy: {
      reason: "test",
      tags: [],
      mood: "tension",
      intensity: 0.5,
      cue_points: []
    },
    anarchy_level_end: 1,
    alignment_warnings: [],
    ...overrides
  };
}

describe("teil2TextSyncPlayback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    playBlob.mockImplementation((_blob, hooks) => {
      hooks?.onPlay?.();
      hooks?.onTimeUpdate?.(0.5, 1);
      return Promise.resolve();
    });
  });

  it("starts avatar chain at show open (not from TTS text position)", async () => {
    const plan = basePlan({});
    const corpus: SceneCorpus = {
      id: "corpus-1",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: plan.sentences.join(" ")
    };

    const updates: Array<Record<string, unknown>> = [];
    await runTextSyncPlayback(
      corpus,
      plan,
      "narrator",
      true,
      (patch) => updates.push(patch),
      () => false
    );

    expect(fireInitialAvatarSegments).toHaveBeenCalled();
    expect(scheduleAvatarSegmentsAtPosition).not.toHaveBeenCalled();
    expect(countUnfiredAvatarSegments).toHaveBeenCalled();
    expect(resolveSentenceSpeech).toHaveBeenCalledTimes(2);
    expect(updates.some((patch) => patch.completed === true)).toBe(true);
  });

  it("does not schedule avatar OSC from onTimeUpdate", async () => {
    const scriptText = "Einleitung. Hier kommt der Bärenklauer und noch mehr Text danach.";
    const plan = basePlan({
      sentences: ["Einleitung.", scriptText.slice(scriptText.indexOf("Hier"))],
      sentence_char_starts: [0, scriptText.indexOf("Hier")],
      avatar_segments: [
        {
          csv_cue_ids: ["BK1_Caro"],
          text_excerpt: "Hier kommt der Bärenklauer",
          char_offset: scriptText.indexOf("Bärenklauer"),
          start_sentence_index: 1,
          end_sentence_index: 1,
          avatar_layers: []
        }
      ]
    });
    const corpus: SceneCorpus = {
      id: "corpus-2",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: scriptText
    };

    await runTextSyncPlayback(corpus, plan, "narrator", true, () => undefined, () => false);

    expect(scheduleAvatarSegmentsAtPosition).not.toHaveBeenCalled();
  });

  it("fires atmosphere time cues during playback", async () => {
    const { postDirectorExecute } = await import("@/lib/api/director");
    const plan = basePlan({
      atmosphere_cue_points: [
        {
          trigger: "time",
          time_offset_sec: 0.3,
          function: "atmosphaere",
          intensity: 0.5,
          visual: { clip_id: "clyde", projector: "adam", video_type: "atmosphere" }
        }
      ]
    });
    const corpus: SceneCorpus = {
      id: "corpus-atmo",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: plan.sentences.join(" ")
    };

    await runTextSyncPlayback(corpus, plan, "narrator", true, () => undefined, () => false);

    const atmosphereCalls = vi
      .mocked(postDirectorExecute)
      .mock.calls.filter((call) => call[0]?.visual?.clip_id === "clyde");
    expect(atmosphereCalls.length).toBeGreaterThanOrEqual(1);
  });

  it("fires atmosphere cues again after abort and restart from start", async () => {
    const { postDirectorExecute } = await import("@/lib/api/director");
    const plan = basePlan({
      atmosphere_cue_points: [
        {
          trigger: "time",
          time_offset_sec: 0.3,
          function: "atmosphaere",
          intensity: 0.5,
          visual: { clip_id: "clyde", projector: "adam", video_type: "atmosphere" }
        }
      ]
    });
    const corpus: SceneCorpus = {
      id: "corpus-restart-atmo",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: plan.sentences.join(" ")
    };

    let generation = 0;
    const shouldAbort = () => generation > 0;
    const first = runTextSyncPlayback(corpus, plan, "narrator", true, () => undefined, shouldAbort);
    await vi.waitFor(() => {
      expect(postDirectorExecute).toHaveBeenCalled();
    });
    generation = 1;
    await first;

    vi.mocked(postDirectorExecute).mockClear();
    await runTextSyncPlayback(corpus, plan, "narrator", true, () => undefined, () => false);

    const atmosphereCalls = vi
      .mocked(postDirectorExecute)
      .mock.calls.filter((call) => call[0]?.visual?.clip_id === "clyde");
    expect(atmosphereCalls.length).toBeGreaterThanOrEqual(1);
  });

  it("starts from a given sentence index", async () => {
    const plan = basePlan({});
    const corpus: SceneCorpus = {
      id: "corpus-3",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: plan.sentences.join(" ")
    };

    await runTextSyncPlayback(corpus, plan, "narrator", true, () => undefined, () => false, {
      startSentenceIndex: 1
    });

    expect(resolveSentenceSpeech).toHaveBeenCalledTimes(1);
    expect(resolveSentenceSpeech).toHaveBeenCalledWith("corpus-3", 1, "Zweiter Satz mit Avatar.", "narrator");
  });

  it("stops after endSentenceIndex when testing a section", async () => {
    const plan = basePlan({});
    const corpus: SceneCorpus = {
      id: "corpus-4",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: plan.sentences.join(" ")
    };

    await runTextSyncPlayback(corpus, plan, "narrator", true, () => undefined, () => false, {
      startSentenceIndex: 0,
      endSentenceIndex: 0
    });

    expect(resolveSentenceSpeech).toHaveBeenCalledTimes(1);
  });

  it("marks earlier avatar segments fired when seeking mid-show", async () => {
    const { markAvatarSegmentsBeforeSentenceIndex, nextUnfiredAvatarInSequence, avatarSegmentKey } =
      await import("@/features/inszenierung/avatarCuePlayback");
    const plan = basePlan({
      sentences: ["Eins.", "Zwei.", "Drei."],
      sentence_char_starts: [0, 5, 10],
      avatar_segments: [
        {
          csv_cue_ids: ["a"],
          text_excerpt: "Eins.",
          char_offset: 0,
          csv_sequence_index: 0,
          start_sentence_index: 0,
          end_sentence_index: 0,
          avatar_layers: []
        },
        {
          csv_cue_ids: ["b"],
          text_excerpt: "Zwei.",
          char_offset: 5,
          csv_sequence_index: 1,
          start_sentence_index: 1,
          end_sentence_index: 1,
          avatar_layers: []
        },
        {
          csv_cue_ids: ["c"],
          text_excerpt: "Drei.",
          char_offset: 10,
          csv_sequence_index: 2,
          start_sentence_index: 2,
          end_sentence_index: 2,
          avatar_layers: []
        }
      ]
    });
    const fired = new Set<string>();
    const marked = markAvatarSegmentsBeforeSentenceIndex(plan, 2, fired);
    expect(marked).toBe(2);
    expect(fired.has(avatarSegmentKey(plan.avatar_segments[0]!))).toBe(true);
    expect(fired.has(avatarSegmentKey(plan.avatar_segments[1]!))).toBe(true);
    expect(nextUnfiredAvatarInSequence(plan, fired, plan.sentence_char_starts)).toMatchObject({
      csv_cue_ids: ["c"]
    });
  });

  it("marks only past time cues when seeking mid-show", async () => {
    const cuePlayback = await import("@/features/show/cuePlayback");
    const markSpy = vi.spyOn(cuePlayback, "markTimeCuesBefore");
    const plan = basePlan({
      sentences: ["Eins.", "Zwei langer Satz hier.", "Drei."],
      sentence_char_starts: [0, 5, 28]
    });
    const corpus: SceneCorpus = {
      id: "corpus-seek-cues",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: plan.sentences.join(" ")
    };

    await runTextSyncPlayback(corpus, plan, "narrator", true, () => undefined, () => false, {
      startSentenceIndex: 1
    });

    expect(markSpy).toHaveBeenCalled();
    const seekClock = markSpy.mock.calls[0]?.[1] as number;
    expect(seekClock).toBeGreaterThan(0);
    for (const call of markSpy.mock.calls) {
      expect(call[1]).toBeLessThan(Number.POSITIVE_INFINITY);
    }
    markSpy.mockRestore();
  });

  it("keeps the live sentence index when aborted mid-run", async () => {
    playBlob.mockImplementation(async (_blob, hooks?: { shouldAbort?: () => boolean }) => {
      while (!hooks?.shouldAbort?.()) {
        await new Promise((r) => setTimeout(r, 10));
      }
    });

    const plan = basePlan({
      sentences: ["Eins.", "Zwei.", "Drei."],
      sentence_char_starts: [0, 5, 10]
    });
    const corpus: SceneCorpus = {
      id: "corpus-abort",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: plan.sentences.join(" ")
    };

    let aborted = false;
    const updates: Array<Record<string, unknown>> = [];
    const run = runTextSyncPlayback(
      corpus,
      plan,
      "narrator",
      true,
      (patch) => updates.push(patch),
      () => aborted
    );

    await vi.waitFor(() => {
      expect(updates.some((u) => u.sentenceIndex === 0)).toBe(true);
    });
    aborted = true;
    await run;

    const final = updates[updates.length - 1];
    expect(final?.running).toBe(false);
    expect(final?.completed).toBe(false);
    expect(final?.sentenceIndex).toBe(0);
  });

  it("skips a sentence when TTS fails and continues the show", async () => {
    const { sleepWallMs } = await import("@/lib/api/client");
    resolveSentenceSpeech
      .mockRejectedValueOnce(new Error("TTS timeout after 45000ms"))
      .mockResolvedValue(new Blob(["audio"]));

    const plan = basePlan({
      sentences: ["Kaputt.", "Weiter."],
      sentence_char_starts: [0, 8]
    });
    const corpus: SceneCorpus = {
      id: "corpus-tts-skip",
      title: "Test",
      scenes: [],
      status: "ready",
      gesamtkonzept: null,
      composition: null,
      teil2_plan: plan,
      script_text: plan.sentences.join(" ")
    };

    const updates: Array<Record<string, unknown>> = [];
    await runTextSyncPlayback(
      corpus,
      plan,
      "narrator",
      true,
      (patch) => updates.push(patch),
      () => false
    );

    expect(sleepWallMs).toHaveBeenCalled();
    expect(resolveSentenceSpeech).toHaveBeenCalledTimes(2);
    expect(playBlob).toHaveBeenCalledTimes(1);
    expect(updates.some((u) => u.completed === true)).toBe(true);
  });
});

describe("estimateNarrationSecondsBefore", () => {
  it("sums character lengths before the seek index", async () => {
    const { estimateNarrationSecondsBefore, NARRATION_CHARS_PER_SEC } = await import(
      "@/features/inszenierung/teil2TextSyncPlayback"
    );
    expect(estimateNarrationSecondsBefore(["abcd", "efgh"], 1)).toBe(4 / NARRATION_CHARS_PER_SEC);
    expect(estimateNarrationSecondsBefore(["abcd", "efgh"], 0)).toBe(0);
    expect(estimateNarrationSecondsBefore(["abcd", "efgh"], 2)).toBe(8 / NARRATION_CHARS_PER_SEC);
  });
});
