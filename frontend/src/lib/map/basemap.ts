/**
 * MAKAN basemap tuning (cartography, not decoration).
 *
 * Following the usual map-design hierarchy: the basemap is quiet context and
 * MAKAN's data (prices, areas, places) is the figure. On the dark theme the
 * OpenFreeMap "dark" style is re-toned onto MAKAN's canvas:
 *   land ≈ the page canvas, so the map reads as part of the product;
 *   water is a deep cyan (the spatial accent, very low chroma) — the Shatt
 *     al-Arab and the Gulf are Basra's defining geography;
 *   roads step up in lightness with importance; buildings barely rise from land;
 *   labels are muted slate with a canvas halo so overlays stay legible.
 * The light theme (OpenFreeMap "liberty") gets the same hierarchy in light
 * tones: white roads on limestone land, pale water, graphite labels.
 *
 * Pure: `basemapOverrides` maps the style's layer list to paint changes, so it
 * is unit-tested without a WebGL map.
 */

export interface LayerInfo {
  id: string;
  type: string;
  "source-layer"?: string;
}

export interface PaintOverride {
  layer: string;
  property: string;
  value: string | number;
}

const LIGHT = {
  land: "#eceeeb",
  landcover: "#e7eae6",
  park: "#dfe8e0",
  water: "#c4dde4",
  waterLine: "#aed0da",
  building: "#e1e3df",
  roadMinor: "#ffffff",
  roadMajor: "#ffffff",
  roadHighway: "#fbf8f1",
  casing: "#d8dbd7",
  aeroway: "#e3e6e2",
  rail: "#d1d5d0",
  boundary: "#aab1b6",
  label: "#697077",
  placeLabel: "#2f353b",
  waterLabel: "#3b7d8e",
  halo: "#f2f3f1",
} as const;

const DARK = {
  land: "#0c0e11",
  landcover: "#0e1114",
  park: "#0f1513",
  water: "#0b1f26",
  waterLine: "#11313b",
  building: "#15181c",
  roadMinor: "#171a1f",
  roadMajor: "#1f232a",
  roadHighway: "#2a2f37",
  casing: "#0c0e11",
  aeroway: "#14171b",
  rail: "#22262d",
  boundary: "#3b4149",
  label: "#6f767f",
  placeLabel: "#a7adb4",
  waterLabel: "#3f8494",
  halo: "#0a0c0f",
} as const;

function has(id: string, ...parts: string[]): boolean {
  return parts.some((p) => id.includes(p));
}

/** Paint changes that put the OpenFreeMap basemap into MAKAN's tones (dark or light). */
export function basemapOverrides(layers: LayerInfo[], dark: boolean): PaintOverride[] {
  const T = dark ? DARK : LIGHT;
  const out: PaintOverride[] = [];
  const set = (layer: string, property: string, value: string | number) =>
    out.push({ layer, property, value });
  for (const layer of layers) {
    const id = layer.id.toLowerCase();
    const source = (layer["source-layer"] ?? "").toLowerCase();
    switch (layer.type) {
      case "background":
        set(layer.id, "background-color", T.land);
        break;
      case "fill":
        if (source === "water" || has(id, "water", "ocean", "sea", "lake", "river")) {
          set(layer.id, "fill-color", T.water);
        } else if (source === "aeroway" || has(id, "aeroway", "runway")) {
          set(layer.id, "fill-color", T.aeroway);
        } else if (source === "building" || has(id, "building")) {
          set(layer.id, "fill-color", T.building);
          set(layer.id, "fill-opacity", 0.9);
        } else if (has(id, "park", "wood", "grass", "forest", "garden")) {
          set(layer.id, "fill-color", T.park);
        } else if (source === "landcover" || source === "landuse" || has(id, "land")) {
          set(layer.id, "fill-color", T.landcover);
        }
        break;
      case "line":
        if (source === "waterway" || has(id, "water", "river", "canal")) {
          set(layer.id, "line-color", T.waterLine);
        } else if (source === "boundary" || has(id, "boundary", "admin")) {
          set(layer.id, "line-color", T.boundary);
        } else if (has(id, "casing", "outline")) {
          // Road edges disappear into the land: the network reads as one quiet mesh.
          set(layer.id, "line-color", T.casing);
        } else if (source === "aeroway" || has(id, "aeroway", "runway", "taxiway")) {
          set(layer.id, "line-color", T.aeroway);
        } else if (has(id, "rail", "transit")) {
          set(layer.id, "line-color", T.rail);
        } else if (
          source === "transportation" ||
          has(id, "road", "highway", "street", "bridge", "tunnel", "path")
        ) {
          if (has(id, "motorway", "trunk", "highway_major", "highway-major")) {
            set(layer.id, "line-color", T.roadHighway);
          } else if (has(id, "primary", "secondary", "major")) {
            set(layer.id, "line-color", T.roadMajor);
          } else {
            set(layer.id, "line-color", T.roadMinor);
          }
        }
        break;
      case "symbol":
        if (source === "place" || has(id, "place", "city", "town")) {
          set(layer.id, "text-color", T.placeLabel);
        } else if (source === "water_name" || has(id, "water")) {
          set(layer.id, "text-color", T.waterLabel);
        } else {
          set(layer.id, "text-color", T.label);
        }
        set(layer.id, "text-halo-color", T.halo);
        break;
      default:
        break;
    }
  }
  return out;
}

/** Apply the overrides; a property a layer does not support is skipped. */
export function applyBasemapTone(
  map: { setPaintProperty: (layer: string, property: string, value: unknown) => void },
  layers: LayerInfo[],
  dark: boolean,
): void {
  for (const { layer, property, value } of basemapOverrides(layers, dark)) {
    try {
      map.setPaintProperty(layer, property, value);
    } catch {
      // A style variant without this paint property: leave the layer as designed.
    }
  }
}
