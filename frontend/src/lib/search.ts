/**
 * URL ⇄ API translation for property search. The browser URL is the source of
 * truth for filters (shareable, back-button friendly); only known keys are
 * forwarded to the API.
 */

export const SEARCH_KEYS = [
  "q",
  "governorate_id",
  "city_id",
  "district_id",
  "neighborhood_id",
  "property_types",
  "purpose",
  "rent_period",
  "currency",
  "min_price",
  "max_price",
  "min_area",
  "max_area",
  "bedrooms_min",
  "bathrooms_min",
  "amenities",
  "furnishing",
  "condition",
  "verified_only",
  "exclude_demo",
  "agency_id",
  "agent_id",
  "posted_within_days",
  "bbox",
  "near_lat",
  "near_lon",
  "radius_km",
  "polygon",
  "sort",
  "page",
  "page_size",
] as const;

const MULTI = new Set(["property_types", "amenities"]);

export type RawParams = Record<string, string | string[] | undefined>;

/** Build the API query string from page searchParams, dropping unknown/empty keys. */
export function toApiQuery(params: RawParams): string {
  const out = new URLSearchParams();
  for (const key of SEARCH_KEYS) {
    const value = params[key];
    if (value === undefined) continue;
    const values = Array.isArray(value) ? value : [value];
    for (const v of values) {
      if (v === "" || v === undefined) continue;
      out.append(key, v);
      if (!MULTI.has(key)) break;
    }
  }
  // A price range without a currency is ambiguous: default to dinars.
  if ((out.has("min_price") || out.has("max_price")) && !out.has("currency")) {
    out.set("currency", "IQD");
  }
  return out.toString();
}

/** Return a new URL query with one key changed (page resets on filter changes). */
export function withParam(params: RawParams, key: string, value: string | string[] | null): string {
  const next: RawParams = { ...params };
  if (value === null || value === "" || (Array.isArray(value) && value.length === 0)) {
    delete next[key];
  } else {
    next[key] = value;
  }
  if (key !== "page") delete next.page;
  return toApiQuery(next);
}

export function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export function all(value: string | string[] | undefined): string[] {
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

/**
 * Canonical API filters (as returned by the search API / saved searches)
 * → a shareable page query string. Defaults are omitted.
 */
export function filtersToQuery(filters: Record<string, unknown>): string {
  const raw: RawParams = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === null || value === undefined || value === false || value === "") continue;
    if (key === "sort" && value === "newest") continue;
    if (key === "bbox" && typeof value === "object" && !Array.isArray(value)) {
      const b = value as Record<string, number>;
      raw.bbox = [b.west, b.south, b.east, b.north].join(",");
    } else if (key === "polygon" && Array.isArray(value)) {
      const ring = value as [number, number][];
      const open = ring.length > 3 && String(ring[0]) === String(ring[ring.length - 1]);
      raw.polygon = (open ? ring.slice(0, -1) : ring)
        .map(([lon, lat]) => `${lon},${lat}`)
        .join(";");
    } else if (Array.isArray(value)) {
      if (value.length) raw[key] = value.map(String);
    } else {
      raw[key] = String(value);
    }
  }
  return toApiQuery(raw);
}
