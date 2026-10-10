/** Small, dependency-free geometry helpers shared by the map UI and tests. */

export type LonLat = [number, number];
export type Bbox = [number, number, number, number];

/** "west,south,east,north" with ~1 m precision (stable URLs, cache friendly). */
export function formatBbox([w, s, e, n]: Bbox): string {
  return [w, s, e, n].map((v) => v.toFixed(5)).join(",");
}

/** API polygon parameter: "lon,lat;lon,lat;..." (open ring; the API closes it). */
export function formatPolygon(points: LonLat[]): string {
  return points.map(([lon, lat]) => `${lon.toFixed(6)},${lat.toFixed(6)}`).join(";");
}

export function parsePolygon(value: string | undefined | null): LonLat[] | null {
  if (!value) return null;
  const points: LonLat[] = [];
  for (const pair of value.split(";")) {
    if (!pair) continue;
    const [lon, lat] = pair.split(",").map(Number);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
    points.push([lon as number, lat as number]);
  }
  return points.length >= 3 ? points : null;
}

export function polygonBbox(points: LonLat[]): Bbox {
  const lons = points.map((p) => p[0]);
  const lats = points.map((p) => p[1]);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}

/** Closed GeoJSON ring for drawing. */
export function closedRing(points: LonLat[]): LonLat[] {
  if (points.length === 0) return [];
  const [firstPoint] = points as [LonLat, ...LonLat[]];
  return [...points, firstPoint];
}

// MapLibre 6 tags nested GeoJSON values with this marker when it serialises
// them for the worker (and parses them back); accept the tagged form as well.
const MAPLIBRE_JSON_TAG = "__$json__";

/** MapLibre stringifies nested GeoJSON properties; accept every form. */
export function readBboxProperty(value: unknown): Bbox | null {
  const text =
    typeof value === "string" && value.startsWith(MAPLIBRE_JSON_TAG)
      ? value.slice(MAPLIBRE_JSON_TAG.length)
      : value;
  const raw = typeof text === "string" ? safeJson(text) : text;
  if (Array.isArray(raw) && raw.length === 4 && raw.every((n) => typeof n === "number")) {
    return raw as Bbox;
  }
  return null;
}

function safeJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}
