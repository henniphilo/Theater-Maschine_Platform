import { describe, expect, it, vi, beforeEach } from "vitest";

import { runTextSyncPlayback } from "@/features/inszenierung/teil2TextSyncPlayback";
import type { SceneCorpus, Teil2PerformancePlan } from "@/lib/types/inszenierung";

const fireAvatarSegmentsAtPosition = vi.fn().mockResolvedValue(undefined);
const fireInitialAvatarSegments = vi.fn().mockResolvedValue(undefined);
const fireRemainingSentenceSegments = vi.fn().mockResolvedValue(undefined);
const countUnfiredAvatarSegments = vi.fn().mockReturnValue(0);
const resolveSentenceSpeech = vi.fn().mockResolvedValue(new Blob(["audio"]));

vi.mock("@/features/inszenierung/avatarCuePlayback", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/inszenierung/avatarCuePlayback")>();
  return {
    ...actual,
    scheduleAvatarSegmentsAtPosition: (...args: unknown[]) => fireAvatarSegmentsAtPosition(...args),
    fireAvatarSegmentsAtPosition: (...args: unknown[]) => fireAvatarSegmentsAtPosition(...args),
    fireInitialAvatarSegments: (...args: unknown[]) => fireInitialAvatarSegments(...args),
    fireRemainingSentenceSegments: (...args: unknown[]) => fireRemainingSentenceSegments(...args),
    countUnfiredAvatarSegments: (...args: unknown[]) => countUnfiredAvatarSegments(...args)
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
  isDirectorPerformanceAborted: () => false,
  isAvatarDoneGateEnabled: vi.fn().mockResolvedValue(false),
  waitForAvatarVideosDone: vi.fn().mockResolvedValue(null)
}));

vi.mock("@/features/show/cuePlayback", () => ({
  createCuePlaybackContext: vi.fn(() => ({
    dramaturgy: {},
    beatText: "",
    fired: new Set(),
    onCommands: vi.fn(),
    shouldAbort: () => false
  })),
  fireSentenceCues: vi.fn(),
  fireStartCues: vi.fn(),
  fireTimeCues: vi.fn(),
  markTimeCuesAsFired: vi.fn(),
  firePerformanceEndCues: vi.fn().mockResolvedValue(undefined)
}));

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

  it("schedules avatar OSC from onTimeUpdate using global text position", async () => {
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

    expect(fireAvatarSegmentsAtPosition).toHaveBeenCalled();
    const maxGlobalPos = Math.max(
      ...fireAvatarSegmentsAtPosition.mock.calls.map((call) => call[1] as number)
    );
    expect(maxGlobalPos).toBeGreaterThanOrEqual(13);
    expect(fireRemainingSentenceSegments).toHaveBeenCalled();
    expect(countUnfiredAvatarSegments).toHaveBeenCalled();
    expect(resolveSentenceSpeech).toHaveBeenCalledTimes(2);
    expect(updates.some((patch) => patch.completed === true)).toBe(true);
  });

  it("does not fire avatar OSC from early onTimeUpdate before char_offset", async () => {
    const scriptText = "Einleitung. Hier kommt der Bärenklauer und noch mehr Text danach.";
    const anchorOffset = scriptText.indexOf("Bärenklauer");
    const plan = basePlan({
      sentences: ["Einleitung.", scriptText.slice(scriptText.indexOf("Hier"))],
      sentence_char_starts: [0, scriptText.indexOf("Hier")],
      avatar_segments: [
        {
          csv_cue_ids: ["BK1_Caro"],
          text_excerpt: "Hier kommt der Bärenklauer",
          char_offset: anchorOffset,
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

    fireAvatarSegmentsAtPosition.mockImplementation(async (_plan, globalPos) => {
      if (globalPos >= anchorOffset) {
        await Promise.resolve();
      }
    });

    playBlob.mockImplementation((_blob, hooks) => {
      hooks?.onTimeUpdate?.(0.05, 1);
      const earlyCalls = fireAvatarSegmentsAtPosition.mock.calls.length;
      const earlyMaxPos = Math.max(
        ...fireAvatarSegmentsAtPosition.mock.calls.map((call) => call[1] as number),
        -1
      );
      expect(earlyMaxPos).toBeLessThan(anchorOffset);
      hooks?.onTimeUpdate?.(0.9, 1);
      expect(fireAvatarSegmentsAtPosition.mock.calls.length).toBeGreaterThan(earlyCalls);
      return Promise.resolve();
    });

    await runTextSyncPlayback(corpus, plan, "narrator", true, () => undefined, () => false);

    const maxPos = Math.max(...fireAvatarSegmentsAtPosition.mock.calls.map((call) => call[1] as number));
    expect(maxPos).toBeGreaterThanOrEqual(anchorOffset);
  });

  it("fires atmosphere time cues during playback", async () => {
    const { fireTimeCues } = await import("@/features/show/cuePlayback");
    const plan = basePlan({
      atmosphere_cue_points: [
        {
          trigger: "time",
          time_offset_sec: 5,
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

    expect(fireTimeCues).toHaveBeenCalled();
    expect(vi.mocked(fireTimeCues).mock.calls.length).toBeGreaterThanOrEqual(2);
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
    const { markAvatarSegmentsBeforeAsFired, nextUnfiredAvatarSegment, avatarSegmentKey } =
      await import("@/features/inszenierung/avatarCuePlayback");
    const plan = basePlan({
      sentences: ["Eins.", "Zwei.", "Drei."],
      sentence_char_starts: [0, 5, 10],
      avatar_segments: [
        {
          csv_cue_ids: ["a"],
          text_excerpt: "Eins.",
          char_offset: 0,
          start_sentence_index: 0,
          end_sentence_index: 0,
          avatar_layers: []
        },
        {
          csv_cue_ids: ["b"],
          text_excerpt: "Zwei.",
          char_offset: 5,
          start_sentence_index: 1,
          end_sentence_index: 1,
          avatar_layers: []
        },
        {
          csv_cue_ids: ["c"],
          text_excerpt: "Drei.",
          char_offset: 10,
          start_sentence_index: 2,
          end_sentence_index: 2,
          avatar_layers: []
        }
      ]
    });
    const fired = new Set<string>();
    const marked = markAvatarSegmentsBeforeAsFired(plan, 10, fired, plan.sentence_char_starts);
    expect(marked).toBe(2);
    expect(fired.has(avatarSegmentKey(plan.avatar_segments[0]!))).toBe(true);
    expect(fired.has(avatarSegmentKey(plan.avatar_segments[1]!))).toBe(true);
    expect(nextUnfiredAvatarSegment(plan, 10, fired, plan.sentence_char_starts)).toMatchObject({
      csv_cue_ids: ["c"]
    });
  });
});
