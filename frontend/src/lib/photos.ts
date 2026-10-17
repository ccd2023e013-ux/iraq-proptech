/**
 * One photograph, one appearance per view (docs/ART-DIRECTION.md, principle 6).
 *
 * DEMO listings draw representative photographs from a small licensed
 * library chosen by property type (backend `demo_images.pick_photo`), so two
 * demo listings of one type often show the same street — which reads as fake.
 * Each listing has its own media URL, so identical photos cannot be told apart
 * by URL here. The rule is therefore: within one view, the first demo listing
 * of each property type shows its photo; later demo listings of that type show
 * a place plate instead. Real listings always show their own photographs.
 */
export function distinctCovers<
  T extends { id: string; cover_url: string | null; is_demo: boolean; property_type_code: string },
>(items: readonly T[]): Map<string, string | null> {
  const seen = new Set<string>();
  const out = new Map<string, string | null>();
  for (const item of items) {
    if (!item.cover_url) {
      out.set(item.id, null);
      continue;
    }
    if (!item.is_demo) {
      out.set(item.id, item.cover_url);
      continue;
    }
    const key = item.property_type_code;
    out.set(item.id, seen.has(key) ? null : item.cover_url);
    seen.add(key);
  }
  return out;
}

/** A glyph for a property type, for the place plate shown instead of a photo. */
export function typeGlyph(code: string): "home" | "building" | "area" | "grid" {
  if (["APARTMENT", "BUILDING", "OFFICE"].includes(code)) return "building";
  if (["LAND", "FARM", "ORCHARD"].includes(code)) return "area";
  if (["SHOP", "WAREHOUSE", "FACTORY", "COMMERCIAL", "OTHER"].includes(code)) return "grid";
  return "home";
}
