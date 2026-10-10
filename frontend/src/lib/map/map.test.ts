import { describe, expect, it } from "vitest";

import {
  closedRing,
  formatBbox,
  formatPolygon,
  parsePolygon,
  polygonBbox,
  readBboxProperty,
} from "./geo";
import { IRAQ_BBOX, parseBbox, parseSatellite, resolveMapConfig } from "./provider";

describe("map provider", () => {
  it("defaults to free OpenFreeMap tiles and the whole of Iraq", () => {
    const config = resolveMapConfig({});
    expect(config.provider).toBe("openfreemap");
    expect(config.style).toMatch(/^https:\/\/tiles\.openfreemap\.org\//);
    expect(config.defaultBbox).toEqual(IRAQ_BBOX);
    expect(config.attribution).toContain("OpenStreetMap");
  });

  it("follows the site theme with the OpenFreeMap dark style", () => {
    expect(resolveMapConfig({}).darkStyle).toBe("https://tiles.openfreemap.org/styles/dark");
    expect(resolveMapConfig({ MAP_PROVIDER: "osm-raster" }).darkStyle).toBeNull();
  });

  it("offers satellite only for an https XYZ source with attribution", () => {
    expect(resolveMapConfig({}).satellite).toBeNull();
    const tiles = "https://imagery.example/{z}/{x}/{y}.jpg?key=public";
    expect(resolveMapConfig({ MAP_SATELLITE_TILES: tiles }).satellite).toBeNull();
    expect(
      resolveMapConfig({ MAP_SATELLITE_TILES: tiles, MAP_SATELLITE_ATTRIBUTION: "© Imagery Co" })
        .satellite,
    ).toEqual({ tiles, attribution: "© Imagery Co" });
    expect(parseSatellite("http://x/{z}/{x}/{y}", "a")).toBeNull();
    expect(parseSatellite("https://x/tiles", "a")).toBeNull();
  });

  it("uses a custom style URL when provided (self-hosting)", () => {
    const config = resolveMapConfig({
      MAP_STYLE_URL: "http://localhost:8080/style.json",
      MAP_ATTRIBUTION: "Self-hosted",
      MAP_DEFAULT_BBOX: "47.6,30.3,48.0,30.7",
    });
    expect(config.provider).toBe("custom");
    expect(config.style).toBe("http://localhost:8080/style.json");
    expect(config.defaultBbox).toEqual([47.6, 30.3, 48.0, 30.7]);
  });

  it("supports a raster OSM fallback without RTL plugin", () => {
    const config = resolveMapConfig({ MAP_PROVIDER: "osm-raster" });
    expect(typeof config.style).toBe("object");
  });

  it("loads no RTL text plugin (MapLibre 6 shapes Arabic itself)", () => {
    for (const env of [{}, { MAP_RTL_PLUGIN_URL: "https://unpkg.com/x/rtl.js" }]) {
      const config = resolveMapConfig(env);
      expect("rtlPluginUrl" in config).toBe(false);
      expect(JSON.stringify(config)).not.toContain("unpkg");
    }
  });

  it("rejects malformed bounding boxes", () => {
    expect(parseBbox("1,2,3")).toBeNull();
    expect(parseBbox("48,30,47,31")).toBeNull(); // west > east
    expect(parseBbox("a,b,c,d")).toBeNull();
    expect(parseBbox("47.7,30.4,47.9,30.6")).toEqual([47.7, 30.4, 47.9, 30.6]);
  });
});

describe("geo helpers", () => {
  const basra: [number, number][] = [
    [47.8, 30.5],
    [47.83, 30.5],
    [47.83, 30.52],
  ];

  it("formats bbox and polygon parameters for the API", () => {
    expect(formatBbox([47.123456789, 30.1, 48, 31])).toBe("47.12346,30.10000,48.00000,31.00000");
    expect(formatPolygon(basra)).toBe(
      "47.800000,30.500000;47.830000,30.500000;47.830000,30.520000",
    );
  });

  it("round-trips polygons and rejects bad input", () => {
    expect(parsePolygon(formatPolygon(basra))).toEqual(basra);
    expect(parsePolygon("47.8,30.5;47.9,30.6")).toBeNull(); // fewer than 3 points
    expect(parsePolygon("x,y;1,2;3,4")).toBeNull();
  });

  it("computes bounds and closes rings", () => {
    expect(polygonBbox(basra)).toEqual([47.8, 30.5, 47.83, 30.52]);
    expect(closedRing(basra)).toHaveLength(4);
    expect(closedRing(basra)[3]).toEqual(basra[0]);
    expect(closedRing([])).toEqual([]);
  });

  it("reads bbox properties stringified by MapLibre", () => {
    expect(readBboxProperty("[47.1,30.1,47.9,30.9]")).toEqual([47.1, 30.1, 47.9, 30.9]);
    expect(readBboxProperty([1, 2, 3, 4])).toEqual([1, 2, 3, 4]);
    expect(readBboxProperty("nope")).toBeNull();
  });

  it("reads bbox properties in MapLibre 6's tagged nested-value form", () => {
    expect(readBboxProperty("__$json__[47.1,30.1,47.9,30.9]")).toEqual([47.1, 30.1, 47.9, 30.9]);
    expect(readBboxProperty("__$json__nope")).toBeNull();
    expect(readBboxProperty("__$json__[1,2,3]")).toBeNull();
    expect(readBboxProperty({ bbox: [1, 2, 3, 4] })).toBeNull();
  });
});
