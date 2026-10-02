import { describe, expect, it } from "vitest";

import { filtersToQuery, toApiQuery, withParam } from "./search";

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

describe("filtersToQuery", () => {
  it("turns canonical API filters into a page query, dropping defaults", () => {
    const query = filtersToQuery({
      q: "شقة",
      purpose: "SALE",
      currency: "IQD",
      max_price: "300000000.00",
      property_types: ["HOUSE", "VILLA"],
      amenities: [],
      verified_only: false,
      exclude_demo: true,
      sort: "newest",
      bbox: { west: 47.7, south: 30.4, east: 47.9, north: 30.6 },
      polygon: null,
    });
    const params = new URLSearchParams(query);
    expect(params.get("q")).toBe("شقة");
    expect(params.getAll("property_types")).toEqual(["HOUSE", "VILLA"]);
    expect(params.get("bbox")).toBe("47.7,30.4,47.9,30.6");
    expect(params.get("exclude_demo")).toBe("true");
    expect(params.has("verified_only")).toBe(false);
    expect(params.has("sort")).toBe(false);
    expect(params.has("amenities")).toBe(false);
  });

  it("opens closed polygon rings for the URL", () => {
    const query = filtersToQuery({
      polygon: [
        [47.8, 30.5],
        [47.9, 30.5],
        [47.85, 30.6],
        [47.8, 30.5],
      ],
    });
    expect(new URLSearchParams(query).get("polygon")).toBe("47.8,30.5;47.9,30.5;47.85,30.6");
  });
});
