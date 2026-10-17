import { describe, expect, it } from "vitest";

import { PhotoRegistry } from "@/features/properties/PhotoSet";

import { typeGlyph } from "./photos";

describe("photo set", () => {
  it("shows a photo once, in reading order, and waits for earlier ones", () => {
    const r = new PhotoRegistry();
    r.set(1, "aaa");
    expect(r.decide(1, "aaa")).toBe("wait"); // slot 0 not known yet
    r.set(0, "aaa");
    expect(r.decide(0, "aaa")).toBe("show");
    expect(r.decide(1, "aaa")).toBe("repeat");
    r.set(2, null); // no photo
    r.set(3, "bbb");
    expect(r.decide(3, "bbb")).toBe("show");
    expect(r.decide(4, undefined)).toBe("wait"); // still loading
    expect(r.decide(4, null)).toBe("show"); // unreadable: treated as unique
  });
});

describe("type glyph", () => {
  it("chooses a glyph by property type", () => {
    expect(typeGlyph("APARTMENT")).toBe("building");
    expect(typeGlyph("LAND")).toBe("area");
    expect(typeGlyph("VILLA")).toBe("home");
  });
});
