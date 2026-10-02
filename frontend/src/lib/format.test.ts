import { describe, expect, it } from "vitest";

import { formatArea, formatCompactPrice, formatPrice } from "./format";

describe("money formatting", () => {
  it("keeps the original currency and never converts", () => {
    expect(formatPrice("250000000", "IQD", "en")).toBe("250,000,000 IQD");
    expect(formatPrice("185000", "USD", "en")).toBe("$185,000");
    expect(formatPrice("185000", "USD", "ar")).toBe("185,000 دولار");
    expect(formatPrice("250000000", "IQD", "ar")).toContain("د.ع");
  });

  it("uses Iraqi 'million' wording for large dinar amounts", () => {
    expect(formatCompactPrice("250000000", "IQD", "ar")).toBe("250 مليون د.ع");
    expect(formatCompactPrice("1500000", "IQD", "en")).toBe("1.5M IQD");
    expect(formatCompactPrice("750000", "IQD", "en")).toBe("750,000 IQD");
  });

  it("returns null for missing values instead of inventing one", () => {
    expect(formatPrice(null, "IQD", "ar")).toBeNull();
    expect(formatArea(null, "ar")).toBeNull();
    expect(formatPrice("abc", "IQD", "en")).toBeNull();
  });

  it("formats areas in square metres", () => {
    expect(formatArea("200.00", "en")).toBe("200 m²");
    expect(formatArea("150.5", "ar")).toBe("150.5 م²");
  });
});
