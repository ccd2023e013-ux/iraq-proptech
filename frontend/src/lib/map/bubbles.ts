/**
 * Price bubbles for the map: pure helpers (no DOM) so they are unit-testable.
 *
 * MapLibre draws a bubble as a symbol whose icon (a stretchable rounded pill
 * rasterised here) is fitted around the price text.
 */

import type { Feature, FeatureCollection } from "geojson";

export type Rgba = [number, number, number, number];

/** "#rgb" / "#rrggbb" → RGBA (alpha 255); anything else → fallback. */
export function parseHex(value: string | null | undefined, fallback: Rgba): Rgba {
  const hex = (value ?? "").trim().replace(/^#/, "");
  if (/^[0-9a-f]{3}$/i.test(hex)) {
    const [r, g, b] = hex.split("").map((c) => parseInt(c + c, 16)) as [number, number, number];
    return [r, g, b, 255];
  }
  if (/^[0-9a-f]{6}$/i.test(hex)) {
    return [
      parseInt(hex.slice(0, 2), 16),
      parseInt(hex.slice(2, 4), 16),
      parseInt(hex.slice(4, 6), 16),
      255,
    ];
  }
  return fallback;
}

export interface PillImage {
  width: number;
  height: number;
  data: Uint8ClampedArray;
  pixelRatio: number;
  stretchX: [number, number][];
  stretchY: [number, number][];
  content: [number, number, number, number];
}

/**
 * A rounded pill with an anti-aliased border, at `ratio` device pixels per CSS
 * pixel. Only the straight middle is stretchable, so the round ends keep
 * their shape for any price length.
 */
export function pillImage(fill: Rgba, stroke: Rgba, ratio = 2): PillImage {
  const height = 26 * ratio;
  const radius = height / 2;
  const width = height + 4 * ratio;
  const border = 1.25 * ratio;
  const data = new Uint8ClampedArray(width * height * 4);
  const cx = width / 2;
  const cy = height / 2;
  const halfInnerX = width / 2 - radius;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      // Signed distance from the pixel centre to the pill outline (negative inside).
      const qx = Math.max(Math.abs(x + 0.5 - cx) - halfInnerX, 0);
      const qy = Math.abs(y + 0.5 - cy);
      const d = Math.hypot(qx, qy) - radius;
      const coverage = Math.min(Math.max(0.5 - d, 0), 1);
      if (coverage === 0) continue;
      const borderMix = Math.min(Math.max(d + border + 0.5, 0), 1);
      const i = (y * width + x) * 4;
      for (let c = 0; c < 3; c++) {
        data[i + c] = Math.round(fill[c]! * (1 - borderMix) + stroke[c]! * borderMix);
      }
      const alpha = fill[3] * (1 - borderMix) + stroke[3] * borderMix;
      data[i + 3] = Math.round(alpha * coverage);
    }
  }
  const mid = width / 2;
  const midY = height / 2;
  return {
    width,
    height,
    data,
    pixelRatio: ratio,
    stretchX: [[mid - ratio, mid + ratio]],
    // Both axes need a stretch zone: MapLibre divides by the stretchable
    // height, so an empty list makes the fitted icon invisible.
    stretchY: [[midY - ratio, midY + ratio]],
    content: [radius * 0.6, 4 * ratio, width - radius * 0.6, height - 4 * ratio],
  };
}

/**
 * Short price for a bubble: Latin digits and currency codes only, because map
 * glyph fonts are not guaranteed to contain Arabic shaping in every style
 * ("$357K", "269M IQD", "1.5M IQD"). The full localized price is in the list
 * and the selection sheet.
 */
export function bubbleLabel(amount: unknown, currency: unknown, onRequest: unknown): string {
  const value = typeof amount === "number" ? amount : Number(amount);
  if (onRequest === true || amount == null || amount === "" || !Number.isFinite(value)) return "—";
  const short = (n: number, unit: string) => {
    const shown = n >= 100 ? Math.round(n).toString() : (Math.round(n * 10) / 10).toString();
    return `${shown}${unit}`;
  };
  const compact =
    value >= 1_000_000_000
      ? short(value / 1_000_000_000, "B")
      : value >= 1_000_000
        ? short(value / 1_000_000, "M")
        : value >= 1_000
          ? short(value / 1_000, "K")
          : String(Math.round(value));
  return currency === "USD" ? `$${compact}` : `${compact} IQD`;
}

const AR_UNITS = { B: "مليار", M: "مليون", K: "ألف" } as const;
const PERIOD = {
  ar: { DAILY: "/يوم", MONTHLY: "/شهر", YEARLY: "/سنة" },
  en: { DAILY: "/day", MONTHLY: "/mo", YEARLY: "/yr" },
} as const;

/**
 * The price on a map tag, in the reader's language: tags are HTML, set in the
 * site's own fonts, so Arabic is written properly ("269 مليون د.ع",
 * "165 ألف دولار/شهر") and English stays compact ("269M IQD", "$165K/mo").
 * Digits are Latin in both, as on the rest of the site.
 */
export function tagLabel(
  amount: unknown,
  currency: unknown,
  onRequest: unknown,
  period: unknown,
  locale: "ar" | "en",
): string {
  const value = typeof amount === "number" ? amount : Number(amount);
  if (onRequest === true || amount == null || amount === "" || !Number.isFinite(value)) return "—";
  const suffix =
    typeof period === "string" && period in PERIOD[locale]
      ? PERIOD[locale][period as keyof (typeof PERIOD)["ar"]]
      : "";
  if (locale === "en") return `${bubbleLabel(value, currency, false)}${suffix}`;
  const short = (n: number) =>
    n >= 100 ? Math.round(n).toString() : (Math.round(n * 10) / 10).toString();
  const [n, unit] =
    value >= 1_000_000_000
      ? [short(value / 1_000_000_000), AR_UNITS.B]
      : value >= 1_000_000
        ? [short(value / 1_000_000), AR_UNITS.M]
        : value >= 1_000
          ? [short(value / 1_000), AR_UNITS.K]
          : [String(Math.round(value)), ""];
  const money = currency === "USD" ? "دولار" : "د.ع";
  return `${[n, unit, money].filter(Boolean).join(" ")}${suffix}`;
}

/** Adds `price_label` to point features; clusters are untouched. */
export function withPriceLabels(collection: FeatureCollection): FeatureCollection {
  const features: Feature[] = collection.features.map((feature) => {
    const p = (feature.properties ?? {}) as Record<string, unknown>;
    if ("point_count" in p || "cluster" in p) return feature;
    return {
      ...feature,
      properties: {
        ...p,
        price_label: bubbleLabel(p.price_amount, p.currency, p.price_on_request),
      },
    };
  });
  return { ...collection, features };
}
