/**
 * Camera paths for the drone flight (pure, unit-tested).
 *
 * A path is a list of camera keyframes; playback interpolates between them
 * with an ease-in-out curve per segment. Bearing takes the shortest turn
 * between keyframes; an orbit is written as explicit quarter turns.
 */

export interface Cam {
  lon: number;
  lat: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export type Preset = "approach" | "orbit" | "reveal";

const M_PER_DEG = 111_320;

/** A point `east` and `north` metres away from (lon, lat). */
export function offsetMetres(
  lon: number,
  lat: number,
  east: number,
  north: number,
): [number, number] {
  return [lon + east / (M_PER_DEG * Math.cos((lat * Math.PI) / 180)), lat + north / M_PER_DEG];
}

/** A square plot of `areaM2` centred on (lon, lat), as a closed ring. */
export function plotRing(lon: number, lat: number, areaM2: number): [number, number][] {
  const half = Math.sqrt(Math.max(36, Math.min(areaM2, 4000))) / 2;
  return [
    offsetMetres(lon, lat, -half, -half),
    offsetMetres(lon, lat, half, -half),
    offsetMetres(lon, lat, half, half),
    offsetMetres(lon, lat, -half, half),
    offsetMetres(lon, lat, -half, -half),
  ];
}

/** Keyframes for a preset around a target; `altitude` shifts every zoom (+ = higher). */
export function presetPath(preset: Preset, lon: number, lat: number, altitude = 0): Cam[] {
  const z = (v: number) => Math.min(19, Math.max(11, v - altitude));
  switch (preset) {
    case "approach": {
      const [sLon, sLat] = offsetMetres(lon, lat, -900, -1100);
      return [
        { lon: sLon, lat: sLat, zoom: z(14.2), pitch: 25, bearing: -35 },
        { lon, lat, zoom: z(17.2), pitch: 60, bearing: 15 },
      ];
    }
    case "orbit":
      return [0, 90, 180, 270, 360].map((bearing) => ({
        lon,
        lat,
        zoom: z(17),
        pitch: 60,
        bearing,
      }));
    case "reveal":
      return [
        { lon, lat, zoom: z(18.2), pitch: 5, bearing: 0 },
        { lon, lat, zoom: z(16.3), pitch: 62, bearing: 120 },
      ];
  }
}

/** Cubic ease-in-out. */
export function easeInOut(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Shortest signed turn from `a` to `b` in degrees (keeps 360° turns written as steps). */
function turn(a: number, b: number): number {
  const d = b - a;
  if (Math.abs(d) <= 180) return d;
  return d > 0 ? d - 360 : d + 360;
}

/**
 * The camera at overall progress `t` (0–1) along `path` (equal time per
 * segment). Segments ease in and out; `linear` keeps a constant pace (orbits).
 */
export function cameraAt(path: Cam[], t: number, linear = false): Cam {
  if (path.length === 0) throw new Error("empty path");
  if (path.length === 1 || t <= 0) return { ...path[0]! };
  if (t >= 1) return { ...path[path.length - 1]! };
  const segments = path.length - 1;
  const at = t * segments;
  const i = Math.min(Math.floor(at), segments - 1);
  const k = linear ? at - i : easeInOut(at - i);
  const a = path[i]!;
  const b = path[i + 1]!;
  // Quarter-turn steps (orbits) keep their direction; other turns go the short way.
  const db =
    Math.abs(b.bearing - a.bearing) === 90 ? b.bearing - a.bearing : turn(a.bearing, b.bearing);
  return {
    lon: lerp(a.lon, b.lon, k),
    lat: lerp(a.lat, b.lat, k),
    zoom: lerp(a.zoom, b.zoom, k),
    pitch: lerp(a.pitch, b.pitch, k),
    bearing: a.bearing + db * k,
  };
}

export type Stage = "site" | "foundations" | "structure" | "envelope" | "complete";

/** Construction stage and building height (m) at progress `t` for a final height. */
export function constructionAt(
  t: number,
  finalHeight: number,
): { stage: Stage; height: number; solid: number } {
  const h = Math.max(3, finalHeight);
  if (t < 0.15) return { stage: "site", height: 0, solid: 0 };
  if (t < 0.3) return { stage: "foundations", height: 0.8, solid: 0.9 };
  if (t < 0.72) {
    const k = easeInOut((t - 0.3) / 0.42);
    return { stage: "structure", height: 0.8 + (h - 0.8) * k, solid: 0.45 };
  }
  if (t < 0.92) return { stage: "envelope", height: h, solid: 0.45 + 0.5 * ((t - 0.72) / 0.2) };
  return { stage: "complete", height: h, solid: 0.95 };
}
