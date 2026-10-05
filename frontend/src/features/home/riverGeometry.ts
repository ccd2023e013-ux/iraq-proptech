/**
 * Schematic geometry for the homepage hero: the courses of the Tigris, the
 * Euphrates and the Shatt al-Arab, and the cities the platform covers. Points
 * are approximate public-knowledge coordinates (lon, lat) — an illustration,
 * not a map: no borders are drawn.
 */

export type LonLat = [number, number];

export const RIVERS: Record<"tigris" | "euphrates" | "shatt", LonLat[]> = {
  tigris: [
    [42.4, 37.07],
    [43.13, 36.34],
    [43.3, 35.6],
    [43.68, 34.6],
    [43.88, 34.2],
    [44.39, 33.32],
    [45.2, 32.95],
    [45.82, 32.51],
    [46.6, 32.2],
    [47.16, 31.84],
    [47.43, 31.0],
  ],
  euphrates: [
    [41.0, 34.4],
    [42.4, 34.1],
    [42.8, 33.6],
    [43.3, 33.42],
    [43.8, 33.35],
    [44.3, 32.8],
    [44.42, 32.48],
    [44.9, 31.99],
    [45.28, 31.31],
    [46.26, 31.04],
    [47.0, 30.95],
    [47.43, 31.0],
  ],
  shatt: [
    [47.43, 31.0],
    [47.6, 30.75],
    [47.81, 30.51],
    [48.0, 30.42],
    [48.25, 30.18],
    [48.48, 29.97],
  ],
};

export interface CityPoint {
  slug: string;
  ar: string;
  en: string;
  at: LonLat;
  /** Label placement relative to the dot. */
  side: "left" | "right";
}

export const CITIES: CityPoint[] = [
  { slug: "mosul", ar: "الموصل", en: "Mosul", at: [43.13, 36.34], side: "left" },
  { slug: "erbil", ar: "أربيل", en: "Erbil", at: [44.01, 36.19], side: "right" },
  { slug: "sulaymaniyah", ar: "السليمانية", en: "Sulaymaniyah", at: [45.43, 35.56], side: "right" },
  { slug: "baghdad", ar: "بغداد", en: "Baghdad", at: [44.37, 33.31], side: "right" },
  { slug: "karbala", ar: "كربلاء", en: "Karbala", at: [44.02, 32.62], side: "left" },
  { slug: "najaf", ar: "النجف", en: "Najaf", at: [44.34, 32.03], side: "left" },
  { slug: "basra", ar: "البصرة", en: "Basra", at: [47.81, 30.51], side: "left" },
];

const BOUNDS = { west: 40.6, east: 48.9, north: 37.3, south: 29.7 };
export const VIEW = { width: 520, height: 476 };

/** Equirectangular projection with a cos(latitude) correction, into the view box. */
export function project([lon, lat]: LonLat): [number, number] {
  const k = Math.cos((33.5 * Math.PI) / 180);
  const spanX = (BOUNDS.east - BOUNDS.west) * k;
  const spanY = BOUNDS.north - BOUNDS.south;
  const scale = Math.min(VIEW.width / spanX, VIEW.height / spanY);
  return [
    Math.round((lon - BOUNDS.west) * k * scale * 10) / 10,
    Math.round((BOUNDS.north - lat) * scale * 10) / 10,
  ];
}

/** Smooth path through points (Catmull–Rom converted to cubic Béziers). */
export function smoothPath(points: LonLat[]): string {
  const p = points.map(project);
  if (p.length < 2) return "";
  let d = `M${p[0]![0]} ${p[0]![1]}`;
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] ?? p[i]!;
    const p1 = p[i]!;
    const p2 = p[i + 1]!;
    const p3 = p[i + 2] ?? p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    const f = (n: number) => Math.round(n * 10) / 10;
    d += ` C${f(c1[0]!)} ${f(c1[1]!)} ${f(c2[0]!)} ${f(c2[1]!)} ${p2[0]} ${p2[1]}`;
  }
  return d;
}
