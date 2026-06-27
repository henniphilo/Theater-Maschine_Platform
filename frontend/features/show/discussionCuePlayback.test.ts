import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  createDiscussionCueContext,
  executeDiscussionCue,
  resolveDiscussionDecision,
  scheduleDiscussionCue
} from "@/features/show/discussionCuePlayback";
import type { DramaturgyDecision } from "@/lib/types/director";

vi.mock("@/lib/api/director", () => ({
  postDirectorDialogueEvent: vi.fn(),
  postDirectorExecute: vi.fn(),
  isDirectorPerformanceAborted: vi.fn(() => false)
}));

import { postDirectorDialogueEvent, postDirectorExecute } from "@/lib/api/director";

const decisionA: DramaturgyDecision = {
  visual: { action: "play_clip", clip_id: "clyde" },
  sound: { action: "trigger_cue", cue_id: "maschinen_grundader" },
  light: { action: "set_scene", scene_id: "vorbuehnenzug" },
  reason: "A",
  tags: [],
  mood: "neutral",
  intensity: 0.5,
  timestamp: 0
};

const decisionB: DramaturgyDecision = {
  ...decisionA,
  sound: { action: "trigger_cue", cue_id: "herz_unter_glas" },
  reason: "B"
};

describe("executeDiscussionCue", () => {
  beforeEach(() => {
    vi.mocked(postDirectorExecute).mockReset();
    vi.mocked(postDirectorExecute).mockResolvedValue({
      executed: true,
      blocked_reason: null,
      osc_commands: [{ bridge: "sound", host: "127.0.0.1", port: 9000, address: "/test", args: [], dry_run: false }]
    });
  });

  it("executes a new discussion cue and skips identical follow-up", async () => {
    const commands: unknown[] = [];
    const ctx = createDiscussionCueContext(async (cmds) => {
      commands.push(cmds);
    }, () => false);

    executeDiscussionCue(ctx, decisionA);
    executeDiscussionCue(ctx, decisionA);
    executeDiscussionCue(ctx, decisionB);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(postDirectorExecute).toHaveBeenCalledTimes(2);
    expect(commands).toHaveLength(2);
  });
});

describe("resolveDiscussionDecision", () => {
  beforeEach(() => {
    vi.mocked(postDirectorDialogueEvent).mockReset();
  });

  it("prefers stored proposed_decision", async () => {
    const turn = {
      speaker: "openai" as const,
      content: "Wir nehmen clyde.",
      proposed_decision: decisionA
    };
    const resolved = await resolveDiscussionDecision(turn, "Stücktext.", "Test");
    expect(resolved).toEqual(decisionA);
    expect(postDirectorDialogueEvent).not.toHaveBeenCalled();
  });
});

describe("scheduleDiscussionCue", () => {
  beforeEach(() => {
    vi.mocked(postDirectorExecute).mockReset();
    vi.mocked(postDirectorExecute).mockResolvedValue({
      executed: true,
      blocked_reason: null,
      osc_commands: []
    });
  });

  it("fires cue in background without blocking on proposed_decision", async () => {
    const ctx = createDiscussionCueContext(async () => undefined, () => false);
    const turn = {
      speaker: "openai" as const,
      content: "Probe.",
      proposed_decision: decisionA
    };

    scheduleDiscussionCue(ctx, turn, "Text", "Thema");
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(postDirectorExecute).toHaveBeenCalled();
  });
});
