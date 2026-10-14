import { validateStyleMin } from "@maplibre/maplibre-gl-style-spec";
import { describe, expect, it } from "vitest";

import { LIMESTONE, NIGHT, OMT_SOURCE, makanStyle, nameField, styleFor } from "./style";

type Layer = {
  id: string;
  type: string;
  source?: string;
  layout?: Record<string, unknown>;
  paint?: Record<string, unknown>;
};

const layersOf = (dark: boolean, lang: "ar" | "en") =>
  (makanStyle({ dark, lang }) as unknown as { layers: Layer[] }).layers;

describe("makanStyle", () => {
  for (const dark of [true, false]) {
    for (const lang of ["ar", "en"] as const) {
      it(`is a valid MapLibre style (${dark ? "night" : "limestone"}, ${lang})`, () => {
        const errors = validateStyleMin(makanStyle({ dark, lang }) as never);
        expect(errors.map((e: { message: string }) => e.message)).toEqual([]);
      });
    }
  }

  it("has unique layer ids that only use the OpenMapTiles source", () => {
    const layers = layersOf(true, "ar");
    expect(new Set(layers.map((l) => l.id)).size).toBe(layers.length);
    for (const l of layers) if (l.type !== "background") expect(l.source).toBe(OMT_SOURCE);
  });

  it("labels in the reader's language only", () => {
    for (const lang of ["ar", "en"] as const) {
      for (const l of layersOf(false, lang).filter((x) => x.type === "symbol")) {
        expect(l.layout?.["text-field"]).toEqual(nameField(lang));
      }
    }
    expect(JSON.stringify(nameField("ar"))).toContain("name:ar");
    expect(JSON.stringify(nameField("ar"))).not.toContain("name:latin");
    expect(JSON.stringify(nameField("en"))).toContain("name:latin");
  });

  it("draws the river glow on the night plate only", () => {
    expect(layersOf(true, "en").some((l) => l.id === "water-glow")).toBe(true);
    expect(layersOf(false, "en").some((l) => l.id === "water-glow")).toBe(false);
  });

  it("keeps land, water and labels apart in both plates", () => {
    for (const P of [NIGHT, LIMESTONE]) {
      expect(P.land).not.toBe(P.water);
      expect(P.land).not.toBe(P.residential);
      expect(P.city).not.toBe(P.halo);
    }
    expect(layersOf(true, "en")[0]?.paint?.["background-color"]).toBe(NIGHT.land);
    expect(layersOf(false, "en")[0]?.paint?.["background-color"]).toBe(LIMESTONE.land);
  });

  it("draws no POI or shop icons", () => {
    expect(layersOf(true, "en").some((l) => l.id.includes("poi"))).toBe(false);
  });
});

describe("styleFor", () => {
  const config = { provider: "openfreemap", style: "https://x/style", darkStyle: "https://x/dark" };
  it("uses MAKAN's plates on OpenFreeMap", () => {
    expect(typeof styleFor(config, true, "ar")).toBe("object");
  });
  it("keeps a configured custom style as given", () => {
    const custom = { ...config, provider: "custom" };
    expect(styleFor(custom, false, "en")).toBe("https://x/style");
    expect(styleFor(custom, true, "en")).toBe("https://x/dark");
  });
});
