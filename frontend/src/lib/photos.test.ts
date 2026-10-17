import { describe, expect, it } from "vitest";

import { distinctCovers, typeGlyph } from "./photos";

const item = (id: string, type: string, demo = true, cover: string | null = `/m/${id}`) => ({
  id,
  cover_url: cover,
  is_demo: demo,
  property_type_code: type,
});

describe("distinct covers", () => {
  it("shows the first demo photo of each type and plates the rest", () => {
    const covers = distinctCovers([
      item("a", "HOUSE"),
      item("b", "HOUSE"),
      item("c", "VILLA"),
      item("d", "HOUSE", false),
      item("e", "LAND", true, null),
    ]);
    expect(covers.get("a")).toBe("/m/a");
    expect(covers.get("b")).toBeNull();
    expect(covers.get("c")).toBe("/m/c");
    expect(covers.get("d")).toBe("/m/d"); // real listings keep their own photos
    expect(covers.get("e")).toBeNull();
  });

  it("chooses a glyph by property type", () => {
    expect(typeGlyph("APARTMENT")).toBe("building");
    expect(typeGlyph("LAND")).toBe("area");
    expect(typeGlyph("VILLA")).toBe("home");
  });
});
