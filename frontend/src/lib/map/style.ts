/**
 * MAKAN's own basemap cartography, built on the free OpenMapTiles vector
 * tiles that OpenFreeMap serves (no key, same data as before).
 *
 * Why a style of our own rather than re-toning a third-party one: the map is
 * MAKAN's signature surface, and its character comes from cartographic
 * decisions a recolour cannot make — which features exist at which zoom, the
 * road hierarchy, one label language, the river drawn as the city's spine.
 *
 * Two plates, one hierarchy:
 *   "Night chart" (dark): navy land, the Shatt al-Arab and its canals as a
 *     lit cyan ribbon with a faint glow, palm groves and marshes as deep
 *     green-teal, buildings as raised blocks from zoom 14, limestone labels.
 *   "Limestone plate" (light): warm paper land, clear blue water with a drawn
 *     shoreline, white streets with warm casings and sand highways, graphite
 *     labels.
 * Labels: one language (the reader's), place names set as a survey plate
 * (spaced capitals for Latin neighbourhoods), roads quiet, no shop or POI
 * icons — MAKAN's own data (prices, places, projects) is the figure.
 *
 * Pure: unit-tested without WebGL.
 */

import type { StyleSpecification } from "maplibre-gl";

export const OMT_SOURCE = "omt";
const TILEJSON = "https://tiles.openfreemap.org/planet";
const GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";

export interface Plate {
  land: string;
  desert: string;
  grove: string;
  park: string;
  wetland: string;
  residential: string;
  works: string;
  building: string;
  buildingLine: string;
  water: string;
  shore: string;
  glow: string | null;
  waterway: string;
  aeroway: string;
  roadMinor: string;
  roadTertiary: string;
  roadSecondary: string;
  roadPrimary: string;
  roadMotorway: string;
  casingMinor: string | null;
  casingMajor: string | null;
  casingMotorway: string | null;
  rail: string;
  border: string;
  borderGov: string;
  city: string;
  district: string;
  road: string;
  waterLabel: string;
  halo: string;
  extrusion: string;
}

export const NIGHT: Plate = {
  land: "#0f1624",
  desert: "#141a24",
  grove: "#0f2121",
  park: "#11251f",
  wetland: "#0e2229",
  residential: "#121b2b",
  works: "#141c2c",
  building: "#192439",
  buildingLine: "#22304a",
  water: "#0a2a3a",
  shore: "#1e5a6e",
  glow: "#22d3ee",
  waterway: "#0e3848",
  aeroway: "#151e30",
  // Streets are neutral slate a step above the land: structure, not wireframe.
  roadMinor: "#1a212d",
  roadTertiary: "#1f2633",
  roadSecondary: "#252d3b",
  roadPrimary: "#2c3545",
  roadMotorway: "#3a4355",
  casingMinor: null,
  casingMajor: null,
  casingMotorway: null,
  rail: "#2a3449",
  border: "#5d6679",
  borderGov: "#38425a",
  city: "#ece6db",
  district: "#9099ab",
  road: "#738098",
  waterLabel: "#56b9cd",
  halo: "#0c121e",
  extrusion: "#1d2a42",
};

export const LIMESTONE: Plate = {
  land: "#f2eee7",
  desert: "#eee6d8",
  grove: "#dde5d0",
  park: "#dfe8d4",
  wetland: "#d6e6e2",
  residential: "#ebe6dd",
  works: "#e7e2da",
  building: "#e3dacd",
  buildingLine: "#d2c6b5",
  water: "#b8d8e4",
  shore: "#8fc0d3",
  glow: null,
  waterway: "#a3cfdf",
  aeroway: "#e6e1d8",
  roadMinor: "#ffffff",
  roadTertiary: "#ffffff",
  roadSecondary: "#fffdf8",
  roadPrimary: "#fff6e3",
  roadMotorway: "#fbe6bd",
  casingMinor: "#e1d9cc",
  casingMajor: "#d7c8b0",
  casingMotorway: "#cba971",
  rail: "#c7beb0",
  border: "#8f8a99",
  borderGov: "#bdb4c2",
  city: "#1d2430",
  district: "#6a7180",
  road: "#7d828b",
  waterLabel: "#3a7a91",
  halo: "#f5f2ec",
  extrusion: "#e4dccf",
};

type Expr = unknown[];

/** The reader's language first; the local name only as a fallback. */
export function nameField(lang: "ar" | "en"): Expr {
  return lang === "ar"
    ? ["coalesce", ["get", "name:ar"], ["get", "name"]]
    : [
        "coalesce",
        ["get", "name:en"],
        ["get", "name_en"],
        ["get", "name:latin"],
        ["get", "name_int"],
        ["get", "name"],
      ];
}

/** Zoom-interpolated width; `add` widens every stop (for casings). */
function width(stops: [number, number][], add = 0): Expr {
  return [
    "interpolate",
    ["exponential", 1.5],
    ["zoom"],
    ...stops.flatMap(([z, w]) => [z, w + add]),
  ];
}

const W = {
  motorway: [
    [5, 0.4],
    [9, 1.2],
    [12, 2.4],
    [15, 6],
    [18, 20],
  ] as [number, number][],
  primary: [
    [7, 0.3],
    [10, 0.9],
    [13, 2],
    [15, 4.5],
    [18, 15],
  ] as [number, number][],
  secondary: [
    [9, 0.3],
    [12, 0.9],
    [14, 2.2],
    [16, 5],
    [18, 11],
  ] as [number, number][],
  minor: [
    [12, 0.3],
    [14, 1],
    [16, 3.2],
    [18, 8],
  ] as [number, number][],
};

const CLASS = {
  motorway: ["motorway", "trunk"],
  primary: ["primary"],
  secondary: ["secondary", "tertiary"],
  minor: ["minor", "service", "street", "residential", "unclassified", "living_street"],
};

function classIs(classes: string[]): Expr {
  return ["match", ["get", "class"], classes, true, false];
}

const REGULAR = ["Noto Sans Regular"];
const BOLD = ["Noto Sans Bold"];
const ITALIC = ["Noto Sans Italic"];

export function makanStyle({
  dark,
  lang,
}: {
  dark: boolean;
  lang: "ar" | "en";
}): StyleSpecification {
  const P = dark ? NIGHT : LIMESTONE;
  const name = nameField(lang);
  const latin = lang === "en";
  const layers: Record<string, unknown>[] = [
    { id: "land", type: "background", paint: { "background-color": P.land } },
    // Ground: desert, palm groves and farmland, marsh — Iraq's real surfaces.
    {
      id: "landcover-desert",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "landcover",
      filter: classIs(["sand", "rock", "bare_rock", "scree"]),
      paint: { "fill-color": P.desert, "fill-antialias": false },
    },
    {
      id: "landcover-grove",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "landcover",
      filter: classIs(["wood", "forest", "farmland", "farm", "orchard"]),
      paint: {
        "fill-color": P.grove,
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.6, 12, 1],
        "fill-antialias": false,
      },
    },
    {
      id: "landcover-wetland",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "landcover",
      filter: classIs(["wetland"]),
      paint: { "fill-color": P.wetland, "fill-antialias": false },
    },
    {
      id: "landcover-grass",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "landcover",
      filter: classIs(["grass"]),
      paint: { "fill-color": P.park, "fill-opacity": 0.7, "fill-antialias": false },
    },
    {
      id: "landuse-residential",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "landuse",
      minzoom: 9,
      filter: classIs(["residential", "suburb", "neighbourhood", "quarter"]),
      paint: {
        "fill-color": P.residential,
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 9, 0.5, 13, 1],
      },
    },
    {
      id: "landuse-works",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "landuse",
      minzoom: 11,
      filter: classIs([
        "commercial",
        "retail",
        "industrial",
        "railway",
        "hospital",
        "school",
        "university",
        "college",
        "military",
      ]),
      paint: { "fill-color": P.works },
    },
    {
      id: "park",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "park",
      minzoom: 10,
      paint: { "fill-color": P.park },
    },
    {
      id: "landuse-green",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "landuse",
      minzoom: 12,
      filter: classIs(["cemetery", "pitch", "stadium", "playground", "garden"]),
      paint: { "fill-color": P.park, "fill-opacity": 0.8 },
    },
    {
      id: "aeroway-area",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "aeroway",
      minzoom: 11,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": P.aeroway },
    },
    // Water: the Shatt al-Arab, the canals and the Gulf are Basra's spine.
    {
      id: "waterway",
      type: "line",
      source: OMT_SOURCE,
      "source-layer": "waterway",
      filter: ["!=", ["get", "brunnel"], "tunnel"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": P.waterway,
        "line-width": [
          "interpolate",
          ["exponential", 1.4],
          ["zoom"],
          8,
          ["match", ["get", "class"], "river", 1, 0.3],
          13,
          ["match", ["get", "class"], "river", 3, "canal", 1.6, 0.7],
          18,
          ["match", ["get", "class"], "river", 12, "canal", 5, 2],
        ],
      },
    },
    {
      id: "water",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "water",
      filter: ["!=", ["get", "brunnel"], "tunnel"],
      paint: { "fill-color": P.water },
    },
    ...(P.glow
      ? [
          {
            // A faint luminous edge on the night plate: the river reads first.
            id: "water-glow",
            type: "line",
            source: OMT_SOURCE,
            "source-layer": "water",
            minzoom: 8,
            paint: {
              "line-color": P.glow,
              "line-opacity": [
                "interpolate",
                ["linear"],
                ["zoom"],
                8,
                0.05,
                11,
                0.1,
                13,
                0.04,
                14,
                0,
              ],
              "line-width": ["interpolate", ["linear"], ["zoom"], 8, 2, 14, 7],
              "line-blur": ["interpolate", ["linear"], ["zoom"], 8, 2, 14, 6],
            },
          },
        ]
      : []),
    {
      id: "water-shore",
      type: "line",
      source: OMT_SOURCE,
      "source-layer": "water",
      minzoom: 9,
      paint: {
        "line-color": P.shore,
        "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.5, 15, 1.2],
        "line-opacity": dark
          ? ["interpolate", ["linear"], ["zoom"], 9, 0.9, 12, 0.6, 14, 0.2, 16, 0.1]
          : 0.9,
      },
    },
    // Buildings: footprints from zoom 14, a drawn edge from 15.
    {
      id: "building",
      type: "fill",
      source: OMT_SOURCE,
      "source-layer": "building",
      minzoom: 14,
      paint: {
        "fill-color": P.building,
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 14, 0, 15, 1],
        "fill-outline-color": P.buildingLine,
      },
    },
    {
      id: "aeroway-runway",
      type: "line",
      source: OMT_SOURCE,
      "source-layer": "aeroway",
      minzoom: 10,
      filter: ["match", ["get", "class"], ["runway", "taxiway"], true, false],
      paint: {
        "line-color": P.roadSecondary,
        "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1, 15, 14],
      },
    },
  ];

  // Roads: casings first (light plate only), then fills by importance.
  const road = (
    id: string,
    classes: string[],
    stops: [number, number][],
    color: string,
    casing: string | null,
    minzoom: number,
  ) => {
    const base = {
      type: "line",
      source: OMT_SOURCE,
      "source-layer": "transportation",
      minzoom,
      layout: { "line-cap": "round", "line-join": "round" },
    };
    const filter = ["all", classIs(classes), ["!=", ["get", "brunnel"], "tunnel"]];
    const out: Record<string, unknown>[] = [];
    if (casing) {
      out.push({
        ...base,
        id: `${id}-casing`,
        minzoom: Math.max(minzoom, 11),
        filter,
        paint: { "line-color": casing, "line-width": width(stops, 1.4) },
      });
    }
    out.push({ ...base, id, filter, paint: { "line-color": color, "line-width": width(stops) } });
    return out;
  };
  const casings: Record<string, unknown>[] = [];
  const fills: Record<string, unknown>[] = [];
  for (const group of [
    road("road-minor", CLASS.minor, W.minor, P.roadMinor, P.casingMinor, 12),
    road("road-secondary", CLASS.secondary, W.secondary, P.roadSecondary, P.casingMajor, 9),
    road("road-primary", CLASS.primary, W.primary, P.roadPrimary, P.casingMajor, 7),
    road("road-motorway", CLASS.motorway, W.motorway, P.roadMotorway, P.casingMotorway, 5),
  ]) {
    for (const layer of group) {
      if (String(layer.id).endsWith("-casing")) casings.push(layer);
      else fills.push(layer);
    }
  }
  layers.push(
    {
      id: "road-path",
      type: "line",
      source: OMT_SOURCE,
      "source-layer": "transportation",
      minzoom: 15,
      filter: classIs(["path", "track", "pedestrian"]),
      paint: {
        "line-color": P.roadTertiary,
        "line-width": ["interpolate", ["linear"], ["zoom"], 15, 0.6, 18, 1.6],
        "line-dasharray": [2, 1.5],
      },
    },
    ...casings,
    ...fills,
    {
      id: "rail",
      type: "line",
      source: OMT_SOURCE,
      "source-layer": "transportation",
      minzoom: 10,
      filter: classIs(["rail", "transit"]),
      paint: {
        "line-color": P.rail,
        "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.6, 16, 1.6],
        "line-dasharray": [3, 2],
      },
    },
    // Boundaries: the national border clearly, governorates faintly.
    {
      id: "border-governorate",
      type: "line",
      source: OMT_SOURCE,
      "source-layer": "boundary",
      minzoom: 5,
      filter: ["all", ["==", ["get", "admin_level"], 4], ["!=", ["get", "maritime"], 1]],
      paint: {
        "line-color": P.borderGov,
        "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.6, 12, 1.2],
        "line-dasharray": [4, 2, 1, 2],
      },
    },
    {
      id: "border-country",
      type: "line",
      source: OMT_SOURCE,
      "source-layer": "boundary",
      filter: ["all", ["==", ["get", "admin_level"], 2], ["!=", ["get", "maritime"], 1]],
      paint: {
        "line-color": P.border,
        "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.8, 10, 1.8],
      },
    },
  );

  // Labels — one language, quiet roads, a survey plate's place names.
  const halo = { "text-halo-color": P.halo, "text-halo-width": 1.3, "text-halo-blur": 0.4 };
  layers.push(
    {
      id: "label-waterway",
      type: "symbol",
      source: OMT_SOURCE,
      "source-layer": "waterway",
      minzoom: 11,
      filter: classIs(["river", "canal"]),
      layout: {
        "symbol-placement": "line",
        "text-field": name,
        "text-font": ITALIC,
        "text-size": ["interpolate", ["linear"], ["zoom"], 11, 11, 16, 14],
        "text-letter-spacing": latin ? 0.08 : 0,
        "symbol-spacing": 420,
        "text-max-angle": 30,
      },
      paint: { "text-color": P.waterLabel, ...halo },
    },
    {
      id: "label-water",
      type: "symbol",
      source: OMT_SOURCE,
      "source-layer": "water_name",
      layout: {
        "text-field": name,
        "text-font": ITALIC,
        "text-size": ["match", ["get", "class"], ["ocean", "sea"], 15, 12],
        "text-letter-spacing": latin ? 0.12 : 0,
        "text-max-width": 8,
      },
      paint: { "text-color": P.waterLabel, ...halo },
    },
    {
      id: "label-road",
      type: "symbol",
      source: OMT_SOURCE,
      "source-layer": "transportation_name",
      minzoom: 14,
      filter: classIs([...CLASS.motorway, ...CLASS.primary, ...CLASS.secondary, ...CLASS.minor]),
      layout: {
        "symbol-placement": "line",
        "text-field": name,
        "text-font": REGULAR,
        "text-size": ["interpolate", ["linear"], ["zoom"], 14, 10.5, 18, 13],
        "symbol-spacing": 360,
        "text-max-angle": 30,
        "text-padding": 6,
      },
      paint: { "text-color": P.road, ...halo },
    },
    {
      id: "label-district",
      type: "symbol",
      source: OMT_SOURCE,
      "source-layer": "place",
      minzoom: 11,
      filter: classIs(["suburb", "quarter", "neighbourhood", "hamlet", "isolated_dwelling"]),
      layout: {
        "text-field": name,
        "text-font": latin ? BOLD : REGULAR,
        "text-size": [
          "interpolate",
          ["linear"],
          ["zoom"],
          11,
          ["match", ["get", "class"], "suburb", 10.5, 9.5],
          15,
          ["match", ["get", "class"], "suburb", 13, 12],
        ],
        "text-transform": latin ? "uppercase" : "none",
        "text-letter-spacing": latin ? 0.1 : 0,
        "text-max-width": 7,
        "text-padding": 10,
      },
      paint: { "text-color": P.district, ...halo },
    },
    {
      id: "label-village",
      type: "symbol",
      source: OMT_SOURCE,
      "source-layer": "place",
      minzoom: 9,
      filter: classIs(["village"]),
      layout: {
        "text-field": name,
        "text-font": REGULAR,
        "text-size": ["interpolate", ["linear"], ["zoom"], 9, 10.5, 14, 13],
        "text-max-width": 7,
        "text-padding": 8,
      },
      paint: { "text-color": P.district, ...halo },
    },
    {
      id: "label-town",
      type: "symbol",
      source: OMT_SOURCE,
      "source-layer": "place",
      minzoom: 6,
      filter: classIs(["town"]),
      layout: {
        "text-field": name,
        "text-font": BOLD,
        "text-size": ["interpolate", ["linear"], ["zoom"], 6, 11, 12, 15],
        "text-letter-spacing": latin ? 0.02 : 0,
        "text-max-width": 8,
      },
      paint: { "text-color": P.city, ...halo },
    },
    {
      id: "label-city",
      type: "symbol",
      source: OMT_SOURCE,
      "source-layer": "place",
      minzoom: 4,
      maxzoom: 14,
      filter: classIs(["city"]),
      layout: {
        "text-field": name,
        "text-font": BOLD,
        "text-size": ["interpolate", ["linear"], ["zoom"], 4, 12, 8, 16, 12, 22],
        "text-letter-spacing": latin ? 0.04 : 0,
        "text-max-width": 8,
      },
      paint: {
        "text-color": P.city,
        // Fades as the city fills the screen: the districts take over.
        "text-opacity": ["interpolate", ["linear"], ["zoom"], 11, 1, 13.5, 0.35],
        ...halo,
      },
    },
    {
      id: "label-country",
      type: "symbol",
      source: OMT_SOURCE,
      "source-layer": "place",
      maxzoom: 7,
      filter: classIs(["country"]),
      layout: {
        "text-field": name,
        "text-font": BOLD,
        "text-size": ["interpolate", ["linear"], ["zoom"], 3, 12, 6, 17],
        "text-transform": latin ? "uppercase" : "none",
        "text-letter-spacing": latin ? 0.18 : 0,
      },
      paint: { "text-color": P.district, ...halo },
    },
  );

  return {
    version: 8,
    name: dark ? "MAKAN Night chart" : "MAKAN Limestone plate",
    glyphs: GLYPHS,
    sources: { [OMT_SOURCE]: { type: "vector", url: TILEJSON } },
    layers,
  } as unknown as StyleSpecification;
}

/** The plate for extruded buildings (3D), matching the current basemap. */
export function extrusionColor(dark: boolean): string {
  return (dark ? NIGHT : LIMESTONE).extrusion;
}

/** The style to load: MAKAN's plates on OpenFreeMap; configured styles as given. */
export function styleFor(
  config: {
    provider: string;
    style: string | Record<string, unknown>;
    darkStyle: string | Record<string, unknown> | null;
  },
  dark: boolean,
  lang: "ar" | "en",
): string | StyleSpecification {
  if (config.provider === "openfreemap") return makanStyle({ dark, lang });
  return ((dark && config.darkStyle) || config.style) as string | StyleSpecification;
}
