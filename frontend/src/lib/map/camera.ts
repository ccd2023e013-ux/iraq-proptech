/**
 * Camera motion for the map (pure, unit-tested).
 *
 * Moves are eases, not flights: selecting a listing glides to it in about
 * 0.8 s, changes zoom by at most two levels, never touches bearing, and keeps
 * the listing in the open part of the map (beside the results rail, above a
 * bottom card). Under prefers-reduced-motion every move is instant.
 */

/** CSS-style cubic-bezier(x1, y1, x2, y2) as an easing function t → progress. */
export function cubicBezier(x1: number, y1: number, x2: number, y2: number) {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;
  const sampleX = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sampleY = (t: number) => ((ay * t + by) * t + cy) * t;
  const slopeX = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  return (x: number): number => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) {
      const err = sampleX(t) - x;
      if (Math.abs(err) < 1e-6) break;
      const d = slopeX(t);
      if (Math.abs(d) < 1e-6) break;
      t -= err / d;
    }
    // Newton can leave [0, 1] near flat ends: fall back to bisection there.
    if (t < 0 || t > 1) {
      let lo = 0;
      let hi = 1;
      t = x;
      for (let i = 0; i < 30; i++) {
        const v = sampleX(t);
        if (Math.abs(v - x) < 1e-6) break;
        if (v < x) lo = t;
        else hi = t;
        t = (lo + hi) / 2;
      }
    }
    return sampleY(t);
  };
}

/** --ease-standard: quick start, long gentle settle. */
export const easeStandard = cubicBezier(0.2, 0, 0, 1);

export const CAMERA_MS = 800;

/** The zoom to settle at when focusing one listing from `current`. */
export function focusZoom(current: number): number {
  if (current >= 14) return current;
  return Math.min(current + 2, 15);
}

/**
 * Pixel offset that centres a point in the open part of the map: half the
 * rail's width towards the end side, and half the bottom card's height up.
 */
export function openAreaOffset(
  railWidth: number,
  bottomCover: number,
  rtl: boolean,
): [number, number] {
  const x = Math.round(railWidth / 2) * (rtl ? -1 : 1);
  return [x === 0 ? 0 : x, bottomCover > 0 ? -Math.round(bottomCover / 2) : 0];
}

/** Duration for a camera move: 0 when the reader asked for reduced motion. */
export function cameraDuration(reducedMotion: boolean, ms = CAMERA_MS): number {
  return reducedMotion ? 0 : ms;
}

export interface TagBox {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  /** Selected or highlighted tags are always placed. */
  pinned?: boolean;
}

/**
 * Greedy collision pass for price tags: pinned tags first, then the rest in
 * the given order; a tag that would overlap one already placed (with `gap`
 * pixels of air) is skipped — its exact spot is still marked by a dot.
 */
export function placeTags(boxes: TagBox[], limit: number, gap = 4): Set<string> {
  const placed: TagBox[] = [];
  const out = new Set<string>();
  const ordered = [...boxes.filter((b) => b.pinned), ...boxes.filter((b) => !b.pinned)];
  for (const b of ordered) {
    if (out.size >= limit && !b.pinned) break;
    const hit = placed.some(
      (p) =>
        b.x < p.x + p.width + gap &&
        b.x + b.width + gap > p.x &&
        b.y < p.y + p.height + gap &&
        b.y + b.height + gap > p.y,
    );
    if (hit && !b.pinned) continue;
    placed.push(b);
    out.add(b.id);
  }
  return out;
}
