import { describe, expect, it } from "vitest";

import { dramaturgSpeakerLabel } from "@/lib/types/script";
import type { DiscussionTurn } from "@/lib/types/script";

export function discussionTurnOrder(turns: DiscussionTurn[]): string[] {
  return turns.map((t) => t.speaker);
}

describe("dramaturgSpeakerLabel", () => {
  it("labels GPT and Claude dramaturgs", () => {
    expect(dramaturgSpeakerLabel("openai")).toBe("ChatGPT");
    expect(dramaturgSpeakerLabel("anthropic")).toBe("Claude");
  });
});

describe("discussionTurnOrder", () => {
  it("preserves alternating speaker sequence", () => {
    const turns: DiscussionTurn[] = [
      { speaker: "openai", content: "a" },
      { speaker: "anthropic", content: "b" },
      { speaker: "openai", content: "c" },
      { speaker: "anthropic", content: "d" }
    ];
    expect(discussionTurnOrder(turns)).toEqual(["openai", "anthropic", "openai", "anthropic"]);
  });
});
