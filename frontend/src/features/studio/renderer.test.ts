import { describe, expect, it } from "vitest";

import { getDictionary } from "@/i18n";

import { compress, pickMimeType, type Storyboard, timeline } from "./renderer";
import { buildTexts } from "./texts";

const sb: Storyboard = {
  version: 1,
  format: "landscape",
  size: [1920, 1080],
  fps: 30,
  is_demo: true,
  property: {
    id: "p",
    reference_code: "BSR-0000001",
    path: "/properties/p",
    title_ar: "بيت للبيع",
    title_en: "House for sale",
    type_ar: "بيت",
    type_en: "House",
    purpose: "SALE",
    city_ar: "البصرة",
    city_en: "Basra",
    district_ar: "العشار",
    district_en: "Al-Ashar",
    price_amount: "269000000",
    currency: "IQD",
    rent_period: null,
    area_m2: "150",
    bedrooms: 3,
    bathrooms: 2,
    verified: false,
  },
  scenes: [
    { type: "map_intro", duration_ms: 3500 },
    { type: "photo", duration_ms: 3000, url: "/a.jpg" },
    { type: "facts", duration_ms: 4000 },
    { type: "cta", duration_ms: 3500 },
  ],
};

describe("studio renderer", () => {
  it("places a drone clip after the map intro and caps its length", () => {
    const t = timeline(sb.scenes, 20_000);
    expect(t.map((x) => x.scene.type)).toEqual(["map_intro", "drone", "photo", "facts", "cta"]);
    expect(t[1]!.end - t[1]!.start).toBe(12_000);
    expect(t[t.length - 1]!.end).toBe(3500 + 12_000 + 3000 + 4000 + 3500);
    expect(timeline(sb.scenes, null)).toHaveLength(4);
  });

  it("compresses for quick previews with a floor", () => {
    expect(compress(sb.scenes, 0.1).every((s) => s.duration_ms >= 600)).toBe(true);
  });

  it("prefers MP4, falls back to WebM, and reports no support", () => {
    expect(pickMimeType((t) => t.startsWith("video/webm"))).toBe("video/webm;codecs=vp9");
    expect(pickMimeType((t) => t === "video/mp4")).toBe("video/mp4");
    expect(pickMimeType(() => false)).toBeNull();
  });

  it("builds captions only from storyboard facts", () => {
    const en = buildTexts(sb, getDictionary("en"), "en", "example.org");
    expect(en.title).toBe("House for sale");
    expect(en.place).toBe("Al-Ashar, Basra");
    expect(en.facts.map((f) => f.label)).toEqual(["Price", "Area", "Bedrooms", "Bathrooms"]);
    expect(en.ctaLine).toContain("BSR-0000001");
    const ar = buildTexts(sb, getDictionary("ar"), "ar", "example.org");
    expect(ar.rtl).toBe(true);
    expect(ar.place).toBe("العشار، البصرة");
  });
});
