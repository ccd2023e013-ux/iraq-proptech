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

const DARK = {
  land: "#0d121c",
  landcover: "#0f1620",
  park: "#0f1a1a",
  water: "#0a2230",
  waterLine: "#0f3442",
  building: "#151c2a",
  roadMinor: "#1a2232",
  roadMajor: "#243047",
  roadHighway: "#2d3c56",
  rail: "#222b3b",
  boundary: "#3a4a63",
  label: "#7c879c",
  placeLabel: "#a3aec2",
  waterLabel: "#3f7f91",
  halo: "#0b0f17",
} as const;

function has(id: string, ...parts: string[]): boolean {
  return parts.some((p) => id.includes(p));
}

/** Paint changes for the dark basemap (empty for other themes). */
export function basemapOverrides(layers: LayerInfo[], dark: boolean): PaintOverride[] {
  if (!dark) return [];
  const out: PaintOverride[] = [];
  const set = (layer: string, property: string, value: string | number) =>
    out.push({ layer, property, value });
  for (const layer of layers) {
    const id = layer.id.toLowerCase();
    const source = (layer["source-layer"] ?? "").toLowerCase();
    switch (layer.type) {
      case "background":
        set(layer.id, "background-color", DARK.land);
        break;
      case "fill":
        if (source === "water" || has(id, "water", "ocean", "sea", "lake", "river")) {
          set(layer.id, "fill-color", DARK.water);
        } else if (source === "building" || has(id, "building")) {
          set(layer.id, "fill-color", DARK.building);
          set(layer.id, "fill-opacity", 0.9);
        } else if (has(id, "park", "wood", "grass", "forest", "garden")) {
          set(layer.id, "fill-color", DARK.park);
        } else if (source === "landcover" || source === "landuse" || has(id, "land")) {
          set(layer.id, "fill-color", DARK.landcover);
        }
        break;
      case "line":
        if (source === "waterway" || has(id, "water", "river", "canal")) {
          set(layer.id, "line-color", DARK.waterLine);
        } else if (source === "boundary" || has(id, "boundary", "admin")) {
          set(layer.id, "line-color", DARK.boundary);
        } else if (has(id, "rail", "transit")) {
          set(layer.id, "line-color", DARK.rail);
        } else if (
          source === "transportation" ||
          has(id, "road", "highway", "street", "bridge", "tunnel", "path")
        ) {
          if (has(id, "motorway", "trunk", "highway_major", "highway-major")) {
            set(layer.id, "line-color", DARK.roadHighway);
          } else if (has(id, "primary", "secondary", "major")) {
            set(layer.id, "line-color", DARK.roadMajor);
          } else {
            set(layer.id, "line-color", DARK.roadMinor);
          }
        }
        break;
      case "symbol":
        if (source === "place" || has(id, "place", "city", "town")) {
          set(layer.id, "text-color", DARK.placeLabel);
        } else if (source === "water_name" || has(id, "water")) {
          set(layer.id, "text-color", DARK.waterLabel);
        } else {
          set(layer.id, "text-color", DARK.label);
        }
        set(layer.id, "text-halo-color", DARK.halo);
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
