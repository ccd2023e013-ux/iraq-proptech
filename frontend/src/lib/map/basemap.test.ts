import { describe, expect, it, vi } from "vitest";

import { applyBasemapTone, basemapOverrides } from "./basemap";

const layers = [
  { id: "background", type: "background" },
  { id: "water", type: "fill", "source-layer": "water" },
  { id: "waterway", type: "line", "source-layer": "waterway" },
  { id: "building", type: "fill", "source-layer": "building" },
  { id: "park", type: "fill", "source-layer": "park" },
  { id: "highway_motorway", type: "line", "source-layer": "transportation" },
  { id: "highway_primary", type: "line", "source-layer": "transportation" },
  { id: "highway_minor", type: "line", "source-layer": "transportation" },
  { id: "highway_primary_casing", type: "line", "source-layer": "transportation" },
  { id: "aeroway_runway", type: "line", "source-layer": "aeroway" },
  { id: "place_city", type: "symbol", "source-layer": "place" },
  { id: "poi_label", type: "symbol", "source-layer": "poi" },
  { id: "hillshade", type: "hillshade" },
];

const value = (layer: string, property: string) =>
  basemapOverrides(layers, true).find((o) => o.layer === layer && o.property === property)?.value;

describe("basemap tone", () => {
  it("tones the light basemap too: white roads on soft grey land, pale water", () => {
    const light = (layer: string, property: string) =>
      basemapOverrides(layers, false).find((o) => o.layer === layer && o.property === property)
        ?.value;
    expect(light("background", "background-color")).toBe("#f4f6f9");
    expect(light("highway_minor", "line-color")).toBe("#ffffff");
    expect(light("water", "fill-color")).toBe("#cce5ee");
    expect(light("poi_label", "text-halo-color")).toBe("#ffffff");
  });

  it("puts land on the canvas, tints water, and steps roads by importance", () => {
    expect(value("background", "background-color")).toBe("#0d121c");
    expect(value("water", "fill-color")).toBe("#0a2230");
    expect(value("waterway", "line-color")).toBe("#0f3442");
    const lightness = (hex: string) =>
      parseInt(hex.slice(1, 3), 16) + parseInt(hex.slice(3, 5), 16);
    const motorway = lightness(String(value("highway_motorway", "line-color")));
    const primary = lightness(String(value("highway_primary", "line-color")));
    const minor = lightness(String(value("highway_minor", "line-color")));
    expect(motorway).toBeGreaterThan(primary);
    expect(primary).toBeGreaterThan(minor);
  });

  it("hides road casings in the land and quiets runways", () => {
    expect(value("highway_primary_casing", "line-color")).toBe("#0d121c");
    expect(value("aeroway_runway", "line-color")).toBe("#151c29");
  });

  it("mutes labels but keeps place names brighter, with a canvas halo", () => {
    expect(value("place_city", "text-color")).toBe("#a3aec2");
    expect(value("poi_label", "text-color")).toBe("#7c879c");
    expect(value("poi_label", "text-halo-color")).toBe("#0b0f17");
    expect(value("hillshade", "text-color")).toBeUndefined();
  });

  it("skips paint properties a layer does not support", () => {
    const setPaintProperty = vi.fn((layer: string) => {
      if (layer === "water") throw new Error("unsupported");
    });
    expect(() => applyBasemapTone({ setPaintProperty }, layers, true)).not.toThrow();
    expect(setPaintProperty).toHaveBeenCalledWith("background", "background-color", "#0d121c");
  });
});
