import { describe, expect, it } from "vitest";

import {
  activeAvatarSegmentIndex,
  avatarSegmentLabel,
  indexOfAvatarSegment
} from "@/features/inszenierung/teil2AvatarSections";
import type { AvatarTextSegment } from "@/lib/types/inszenierung";

function segment(overrides: Partial<AvatarTextSegment> = {}): AvatarTextSegment {
  return {
    csv_cue_ids: ["thiemo"],
    text_excerpt: "die Kurse steigen rasant",
    char_offset: 10,
    start_sentence_index: 2,
    end_sentence_index: 4,
    avatar_layers: [{ avatar_speech_id: "thiemo", avatar: "delphin", video_clip_id: "Thiemo" }],
    ...overrides
  };
}

describe("teil2AvatarSections", () => {
  it("labels segment from video clip ids", () => {
    expect(avatarSegmentLabel(segment())).toBe("Thiemo");
  });

  it("finds active segment for sentence index", () => {
    const segments = [
      segment({ start_sentence_index: 0, end_sentence_index: 1 }),
      segment({ start_sentence_index: 2, end_sentence_index: 4, csv_cue_ids: ["branko"] })
    ];
    expect(activeAvatarSegmentIndex(segments, 3)).toBe(1);
    expect(activeAvatarSegmentIndex(segments, 9)).toBe(-1);
  });

  it("finds chain segment by identity even when sentence spans differ", () => {
    const segments = [
      segment({ csv_sequence_index: 0, csv_cue_ids: ["a"], char_offset: 0 }),
      segment({
        csv_sequence_index: 1,
        csv_cue_ids: ["b"],
        char_offset: 40,
        text_excerpt: "nächster Avatar",
        avatar_layers: [{ avatar_speech_id: "b", avatar: "wolf", video_clip_id: "Wolf" }]
      })
    ];
    expect(indexOfAvatarSegment(segments, segments[1])).toBe(1);
    expect(indexOfAvatarSegment(segments, null)).toBe(-1);
  });
});
