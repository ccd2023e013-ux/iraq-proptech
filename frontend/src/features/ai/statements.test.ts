import { describe, expect, it } from "vitest";

import { getDictionary } from "@/i18n";
import type { Statement } from "@/types/intelligence";

import { badgeKind, renderStatement } from "./statements";

const en = getDictionary("en");
const ar = getDictionary("ar");

function st(partial: Partial<Statement>): Statement {
  return {
    kind: "FACT",
    origin: "listing",
    section: "facts",
    key: "fact.area",
    params: {},
    text: null,
    source: "listing",
    confidence: null,
    ...partial,
  };
}

describe("intelligence statements", () => {
  it("renders facts and estimates from keys in both languages", () => {
    expect(renderStatement(st({ params: { area_m2: "200" } }), en, "en")).toBe("Area 200 m²");
    expect(renderStatement(st({ params: { area_m2: "200" } }), ar, "ar")).toBe("المساحة 200 م²");
    const range = renderStatement(
      st({
        kind: "ESTIMATE",
        origin: "computed",
        section: "price",
        key: "estimate.price_range",
        params: {
          low: "90000",
          high: "120000",
          currency: "USD",
          median_m2: "500",
          count: 6,
          position: "within_range",
        },
      }),
      en,
      "en",
    );
    expect(range).toContain("6 comparable listings");
    expect(range).toContain("within this range");
  });

  it("shows AI text as given and never invents a message for it", () => {
    const ai = st({
      kind: "AI_INTERPRETATION",
      origin: "ai",
      key: "ai.text",
      text: "Plain words.",
    });
    expect(renderStatement(ai, en, "en")).toBe("Plain words.");
    expect(badgeKind("AI_INTERPRETATION")).toBe("ai");
    expect(badgeKind("FACT")).toBe("fact");
  });

  it("marks demo and approximate places", () => {
    const places = st({
      kind: "SOURCE",
      origin: "external",
      section: "neighbourhood",
      key: "source.places_within",
      params: { count: 3, category: "SCHOOL", radius_m: 1500, demo: true },
    });
    expect(renderStatement(places, en, "en")).toBe("3 Schools within 1,500 m (demo places)");
  });

  it("every message key exists in both dictionaries", () => {
    expect(Object.keys(en.intel.m).sort()).toEqual(Object.keys(ar.intel.m).sort());
  });
});
