import { describe, expect, it } from "vitest";

import { toApiQuery, withParam } from "./search";

describe("search URL helpers", () => {
  it("forwards only known, non-empty keys", () => {
    const query = toApiQuery({ q: "العشار", purpose: "SALE", evil: "1", city_id: "" });
    const parsed = new URLSearchParams(query);
    expect(parsed.get("q")).toBe("العشار");
    expect(parsed.get("purpose")).toBe("SALE");
    expect(parsed.has("evil")).toBe(false);
    expect(parsed.has("city_id")).toBe(false);
  });

  it("keeps repeated multi-value keys and collapses single ones", () => {
    const parsed = new URLSearchParams(
      toApiQuery({ property_types: ["HOUSE", "VILLA"], sort: ["price_asc", "newest"] }),
    );
    expect(parsed.getAll("property_types")).toEqual(["HOUSE", "VILLA"]);
    expect(parsed.getAll("sort")).toEqual(["price_asc"]);
  });

  it("defaults the price currency to IQD instead of mixing currencies", () => {
    expect(new URLSearchParams(toApiQuery({ max_price: "200000000" })).get("currency")).toBe("IQD");
    expect(
      new URLSearchParams(toApiQuery({ max_price: "200000", currency: "USD" })).get("currency"),
    ).toBe("USD");
  });

  it("resets pagination when a filter changes", () => {
    const parsed = new URLSearchParams(withParam({ page: "3", q: "x" }, "purpose", "RENT"));
    expect(parsed.has("page")).toBe(false);
    expect(parsed.get("purpose")).toBe("RENT");
    expect(new URLSearchParams(withParam({ page: "3" }, "page", "4")).get("page")).toBe("4");
    expect(new URLSearchParams(withParam({ q: "x" }, "q", null)).has("q")).toBe(false);
  });
});
