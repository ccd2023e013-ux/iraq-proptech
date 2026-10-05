import type { Bbox } from "./geo";

/** Place groups offered in the layers panel (API categories per group). */
export const PLACE_GROUPS: { key: string; categories: string[] }[] = [
  { key: "SCHOOL", categories: ["SCHOOL", "UNIVERSITY"] },
  { key: "HOSPITAL", categories: ["HOSPITAL", "CLINIC", "PHARMACY"] },
  { key: "MOSQUE", categories: ["MOSQUE", "CHURCH"] },
  { key: "MARKET", categories: ["MARKET", "MALL"] },
  { key: "PARK", categories: ["PARK"] },
];

/** The API serves places for city-sized views only (≤ 4 square degrees). */
export function placesAllowed(bbox: Bbox | null): boolean {
  if (!bbox) return false;
  return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) <= 4;
}

/** A square-ish bbox of `km` around a point (for "near me"). */
export function bboxAround(lon: number, lat: number, km: number): Bbox {
  const dLat = km / 111;
  const dLon = km / (111 * Math.max(Math.cos((lat * Math.PI) / 180), 0.2));
  return [lon - dLon, lat - dLat, lon + dLon, lat + dLat];
}
