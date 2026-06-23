import { describe, expect, it } from "vitest";

import { isBaerenklauBeat, part1Beats } from "./baerenklauBeat";
import type { ScriptBeat } from "@/lib/types/script";

function beat(partial: Partial<ScriptBeat> & Pick<ScriptBeat, "id" | "order" | "text">): ScriptBeat {
  return {
    speaker: "AI_A",
    dramaturgy: null,
    planned_commands: [],
    discussion_summary: null,
    ...partial
  };
}

describe("baerenklauBeat", () => {
  it("detects Bärenklau in scene title", () => {
    expect(isBaerenklauBeat(beat({ id: "1", order: 0, text: "Hallo", scene_title: "Szene Bärenklau" }))).toBe(true);
  });

  it("part1Beats returns all beats", () => {
    const beats = [
      beat({ id: "a", order: 0, text: "Delphin" }),
      beat({ id: "b", order: 1, text: "Bärenklau spricht", scene_title: "Bärenklau" })
    ];
    expect(part1Beats(beats).map((b) => b.id)).toEqual(["a", "b"]);
  });

  it("part1Beats returns single whole-text beat", () => {
    const beats = [beat({ id: "a", order: 0, text: "Gesamter Stücktext." })];
    expect(part1Beats(beats).map((b) => b.id)).toEqual(["a"]);
  });
});
