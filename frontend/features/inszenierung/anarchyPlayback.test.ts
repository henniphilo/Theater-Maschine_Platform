import { describe, expect, it } from "vitest";

import type { CompositionMoment } from "@/lib/types/inszenierung";
import type { VisualCue } from "@/lib/types/visual";

import {
  avatarVisualCuesForMoment,
  planRequiresTts
} from "./avatarCuePlayback";
import {
  avatarBeatHoldMs,
  computeMomentDelayMs
} from "./anarchyPlayback";
import { momentSpeechLabel } from "./inszenierungBuffer";

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

  it("does not shorten avatar beat start delay via overlap", () => {
    const avatar = moment({
      speech_mode: "avatar_video",
      start_delay_ms: 1000,
      overlap_with_previous: 0.8
    });
    expect(computeMomentDelayMs(avatar, 1)).toBe(1000);
  });

  it("avatarBeatHoldMs prefers duration_hint_ms then layer visual cues", () => {
    expect(avatarBeatHoldMs(moment({ duration_hint_ms: 420_000 }))).toBe(420_000);
    expect(
      avatarBeatHoldMs(
        moment({
          duration_hint_ms: null,
          avatar_layers: [
            {
              avatar_speech_id: "DEL1",
              avatar: "delphin",
              video_clip_id: "avatar",
              visual_cue: { clip_id: "avatar", action: "play_clip", duration_ms: 90_000 }
            }
          ]
        })
      )
    ).toBe(90_000);
    expect(avatarBeatHoldMs(moment({ duration_hint_ms: null }))).toBe(8000);
  });
});

describe("momentSpeechLabel", () => {
  it("labels avatar and ki modes", () => {
    expect(
      momentSpeechLabel(
        moment({ speech_mode: "avatar_video", avatar_speech_id: "BK3" })
      )
    ).toBe("Avatar BK3");
    expect(
      momentSpeechLabel({
        ...moment({ speech_mode: "avatar_video" }),
        avatar_layers: [
          { avatar_speech_id: "DEL1", avatar: "delphin", video_clip_id: "avatar" },
          { avatar_speech_id: "LG1", avatar: "lamm", video_clip_id: "esel" }
        ]
      })
    ).toBe("Chorus DEL1, LG1");
    expect(momentSpeechLabel(moment({ speech_mode: "tts", speaker: "AI_B" }))).toBe("KI Stimme B");
    expect(momentSpeechLabel(moment({ speech_mode: "silent" }))).toBe("Stumm");
  });
});

describe("avatarCuePlayback", () => {
  it("collects visual cues from avatar layers", () => {
    const visual = { clip_id: "avatar", action: "play_clip" } as VisualCue;
    const cues = avatarVisualCuesForMoment({
      ...moment({ speech_mode: "avatar_video" }),
      avatar_layers: [
        {
          avatar_speech_id: "DEL1",
          avatar: "delphin",
          video_clip_id: "avatar",
          visual_cue: visual
        }
      ]
    });
    expect(cues).toHaveLength(1);
    expect(cues[0].clip_id).toBe("avatar");
  });

  it("avatar-only plan does not require tts", () => {
    expect(
      planRequiresTts({
        moments: [moment({ speech_mode: "avatar_video" })],
        total_estimated_duration_sec: 10,
        max_concurrent_voices: 3,
        max_concurrent_videos: 2
      })
    ).toBe(false);
  });
});
