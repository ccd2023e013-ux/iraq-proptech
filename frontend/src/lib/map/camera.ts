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
  return placeTagsBalanced(boxes, limit, { gap }).shown;
}

export interface Placement {
  /** Tags drawn. */
  shown: Set<string>;
  /** For a drawn tag: how many hidden listings sit close to it ("+N"). */
  more: Map<string, number>;
}

/** Where a tag points: the middle of its lower edge. */
function anchorOf(b: TagBox): [number, number] {
  return [b.x + b.width / 2, b.y + b.height];
}

/**
 * Balanced placement. Greedy collision as `placeTags`, but candidates are
 * taken round-robin across a screen grid of `cell` px, so prices spread over
 * the whole view instead of piling into the first dense neighbourhood. A
 * listing whose tag does not fit is counted on the nearest drawn tag within
 * `absorb` px (shown as "+N"), so no listing is silently dropped.
 */
export function placeTagsBalanced(
  boxes: TagBox[],
  limit: number,
  { gap = 4, cell = 0, absorb = 0 }: { gap?: number; cell?: number; absorb?: number } = {},
): Placement {
  const pinned = boxes.filter((b) => b.pinned);
  let rest = boxes.filter((b) => !b.pinned);
  if (cell > 0 && rest.length > 1) {
    const buckets = new Map<string, TagBox[]>();
    for (const b of rest) {
      const [ax, ay] = anchorOf(b);
      const key = `${Math.floor(ax / cell)}:${Math.floor(ay / cell)}`;
      const list = buckets.get(key);
      if (list) list.push(b);
      else buckets.set(key, [b]);
    }
    const lists = [...buckets.values()];
    const spread: TagBox[] = [];
    for (let round = 0; spread.length < rest.length; round++) {
      for (const list of lists) if (round < list.length) spread.push(list[round]!);
    }
    rest = spread;
  }
  const placed: TagBox[] = [];
  const shown = new Set<string>();
  const hidden: TagBox[] = [];
  for (const b of [...pinned, ...rest]) {
    if (shown.size >= limit && !b.pinned) {
      hidden.push(b);
      continue;
    }
    const hit = placed.some(
      (p) =>
        b.x < p.x + p.width + gap &&
        b.x + b.width + gap > p.x &&
        b.y < p.y + p.height + gap &&
        b.y + b.height + gap > p.y,
    );
    if (hit && !b.pinned) {
      hidden.push(b);
      continue;
    }
    placed.push(b);
    shown.add(b.id);
  }
  const more = new Map<string, number>();
  if (absorb > 0) {
    for (const h of hidden) {
      const [hx, hy] = anchorOf(h);
      let best: TagBox | null = null;
      let bestD = absorb * absorb;
      for (const p of placed) {
        const [px, py] = anchorOf(p);
        const d = (px - hx) ** 2 + (py - hy) ** 2;
        if (d <= bestD) {
          bestD = d;
          best = p;
        }
      }
      if (best) more.set(best.id, (more.get(best.id) ?? 0) + 1);
    }
  }
  return { shown, more };
}
