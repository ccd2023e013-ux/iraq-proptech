import { describe, expect, it } from "vitest";

import { percent, rangeQuery } from "./types";

describe("rangeQuery", () => {
  it("keeps valid dates and the demo flag", () => {
    expect(rangeQuery({ date_from: "2026-05-01", date_to: "2026-05-07", include_demo: "1" })).toBe(
      "date_from=2026-05-01&date_to=2026-05-07&include_demo=true",
    );
  });

  it("drops malformed input and keeps extras", () => {
    expect(rangeQuery({ date_from: "1;DROP", date_to: "" }, { scope: "agency" })).toBe(
      "scope=agency",
    );
  });
});

describe("percent", () => {
  it("formats ratios and missing values", () => {
    expect(percent(0.1234)).toBe("12.3%");
    expect(percent(null)).toBe("—");
  });
});
