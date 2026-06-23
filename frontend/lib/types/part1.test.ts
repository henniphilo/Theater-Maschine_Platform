import { describe, expect, it } from "vitest";

import { resolvePerformancePart } from "./part1";

describe("resolvePerformancePart", () => {
  it("defaults to part1 when unset", () => {
    expect(resolvePerformancePart(null, true)).toBe("part1_baerenklau");
  });

  it("keeps explicit part2", () => {
    expect(resolvePerformancePart("part2_delphin_to_mole", true)).toBe("part2_delphin_to_mole");
  });
});
