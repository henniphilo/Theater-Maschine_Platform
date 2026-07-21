import { describe, expect, it, vi } from "vitest";

import {
  avatarSegmentKey,
  avatarSegmentsDueAtPosition,
  avatarSegmentsInSentence,
  effectiveCharOffset,
  fireAvatarSegmentIfDue,
  fireRemainingSentenceSegments,
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
          char_offset: 0,
          csv_sequence_index: 0,
          start_sentence_index: 0,
          end_sentence_index: 0,
          avatar_layers: []
        },
        {
          csv_cue_ids: ["second"],
          text_excerpt: "gamma",
          char_offset: 12,
          csv_sequence_index: 1,
          start_sentence_index: 1,
          end_sentence_index: 1,
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
  it("pauses narrator until wait resolves when gate enabled", async () => {
    const { isAvatarDoneGateEnabled, waitForAvatarVideosDone } = await import("@/lib/api/director");
    const { setPlaybackPaused } = await import("@/lib/api/client");
    const { fireAvatarSegmentIfDue } = await import("@/features/inszenierung/avatarCuePlayback");

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
    expect(setPlaybackPaused).toHaveBeenCalledWith(true);
    expect(waitForAvatarVideosDone).toHaveBeenCalled();
    expect(setPlaybackPaused).toHaveBeenCalledWith(false);
  });
});
