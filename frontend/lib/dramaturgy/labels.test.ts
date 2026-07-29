import { describe, expect, it } from "vitest";

import { displayReasonShort, dramaturgicalFunctionLabel } from "@/lib/dramaturgy/labels";

describe("dramaturgy labels", () => {
  it("prefers reason_short over reason", () => {
    expect(displayReasonShort("Kurz.", "Lange Begründung.")).toBe("Kurz.");
  });

  it("maps dramaturgical function labels", () => {
    expect(dramaturgicalFunctionLabel("contrast")).toBe("Kontrast");
    expect(dramaturgicalFunctionLabel("space")).toBe("Leerstelle");
  });
});
