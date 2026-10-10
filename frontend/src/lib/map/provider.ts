/**
 * Map provider abstraction. The basemap is configuration, not code: switching
 * from the free OpenFreeMap tiles to a self-hosted style (e.g. PMTiles on the
 * production PC) is an environment change. No paid provider or API key is
 * required by default.
 *
 * Read on the server at request time (not baked into the build):
 *   MAP_PROVIDER     openfreemap (default) | osm-raster | custom
 *   MAP_STYLE_URL    style JSON URL (required for `custom`; overrides others)
 *   MAP_ATTRIBUTION  extra attribution text for custom styles
 *   MAP_DEFAULT_BBOX initial view "west,south,east,north" (default: all of Iraq)
 *   MAP_DARK_STYLE_URL  style used when the site is in dark mode (optional)
 *   MAP_SATELLITE_TILES https raster XYZ template with {z}/{x}/{y} (optional, keyed
 *                       providers only — see docs/MAP-PROVIDERS.md)
 *   MAP_SATELLITE_ATTRIBUTION  required with MAP_SATELLITE_TILES
 *
 * No RTL text plugin: MapLibre 6 shapes Arabic labels itself (the plugin is
 * deprecated, and its worker would have to `eval` it, which the CSP forbids).
 */

export type MapProvider = "openfreemap" | "osm-raster" | "custom";

export interface MapConfig {
  provider: MapProvider;
  /** MapLibre style: a URL, or an inline style object for raster tiles. */
  style: string | Record<string, unknown>;
  /** Style for dark mode; null keeps `style`. */
  darkStyle: string | Record<string, unknown> | null;
  /** Optional imagery layer; only offered when configured with attribution. */
  satellite: { tiles: string; attribution: string } | null;
  attribution: string;
  defaultBbox: [number, number, number, number];
}

/** Iraq's extent (west, south, east, north). */
export const IRAQ_BBOX: [number, number, number, number] = [38.79, 29.06, 48.57, 37.38];

const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const OPENFREEMAP_DARK_STYLE = "https://tiles.openfreemap.org/styles/dark";
const OSM_ATTRIBUTION = "© OpenStreetMap contributors";

function osmRasterStyle(): Record<string, unknown> {
  return {
    version: 8,
    // Glyphs for our own labels (prices, cluster counts); the tiles are raster.
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        maxzoom: 19,
        attribution: OSM_ATTRIBUTION,
      },
    },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  };
}

export function parseBbox(
  value: string | undefined | null,
): [number, number, number, number] | null {
  if (!value) return null;
  const parts = value.split(",").map((v) => Number(v.trim()));
  if (parts.length !== 4 || parts.some((n) => !Number.isFinite(n))) return null;
  const [w, s, e, n] = parts as [number, number, number, number];
  if (w >= e || s >= n || w < -180 || e > 180 || s < -90 || n > 90) return null;
  return [w, s, e, n];
}

/** A satellite source is accepted only as an https XYZ template with attribution. */
export function parseSatellite(
  tiles: string | undefined,
  attribution: string | undefined,
): MapConfig["satellite"] {
  const url = tiles?.trim();
  const credit = attribution?.trim();
  if (!url || !credit) return null;
  if (!url.startsWith("https://")) return null;
  if (!["{z}", "{x}", "{y}"].every((part) => url.includes(part))) return null;
  return { tiles: url, attribution: credit };
}

export function resolveMapConfig(env: Record<string, string | undefined>): MapConfig {
  const requested = (env.MAP_PROVIDER ?? "openfreemap") as MapProvider;
  const styleUrl = env.MAP_STYLE_URL?.trim();
  const defaultBbox = parseBbox(env.MAP_DEFAULT_BBOX) ?? IRAQ_BBOX;
  const satellite = parseSatellite(env.MAP_SATELLITE_TILES, env.MAP_SATELLITE_ATTRIBUTION);
  const darkOverride = env.MAP_DARK_STYLE_URL?.trim() || null;

  if (styleUrl) {
    return {
      provider: "custom",
      style: styleUrl,
      darkStyle: darkOverride,
      satellite,
      attribution: env.MAP_ATTRIBUTION ?? OSM_ATTRIBUTION,
      defaultBbox,
    };
  }
  if (requested === "osm-raster") {
    return {
      provider: "osm-raster",
      style: osmRasterStyle(),
      darkStyle: null,
      satellite,
      attribution: OSM_ATTRIBUTION,
      defaultBbox,
    };
  }
  return {
    provider: "openfreemap",
    style: OPENFREEMAP_STYLE,
    darkStyle: darkOverride ?? OPENFREEMAP_DARK_STYLE,
    satellite,
    attribution: "OpenFreeMap © OpenMapTiles, data © OpenStreetMap contributors",
    defaultBbox,
  };
}
