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
 *   MAP_RTL_PLUGIN_URL  Arabic shaping plugin for vector labels
 */

export type MapProvider = "openfreemap" | "osm-raster" | "custom";

export interface MapConfig {
  provider: MapProvider;
  /** MapLibre style: a URL, or an inline style object for raster tiles. */
  style: string | Record<string, unknown>;
  attribution: string;
  defaultBbox: [number, number, number, number];
  rtlPluginUrl: string | null;
}

/** Iraq's extent (west, south, east, north). */
export const IRAQ_BBOX: [number, number, number, number] = [38.79, 29.06, 48.57, 37.38];

const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const DEFAULT_RTL_PLUGIN =
  "https://unpkg.com/@mapbox/mapbox-gl-rtl-text@0.3.0/dist/mapbox-gl-rtl-text.js";
const OSM_ATTRIBUTION = "© OpenStreetMap contributors";

function osmRasterStyle(): Record<string, unknown> {
  return {
    version: 8,
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

export function resolveMapConfig(env: Record<string, string | undefined>): MapConfig {
  const requested = (env.MAP_PROVIDER ?? "openfreemap") as MapProvider;
  const styleUrl = env.MAP_STYLE_URL?.trim();
  const rtlPluginUrl =
    env.MAP_RTL_PLUGIN_URL === "" ? null : (env.MAP_RTL_PLUGIN_URL ?? DEFAULT_RTL_PLUGIN);
  const defaultBbox = parseBbox(env.MAP_DEFAULT_BBOX) ?? IRAQ_BBOX;

  if (styleUrl) {
    return {
      provider: "custom",
      style: styleUrl,
      attribution: env.MAP_ATTRIBUTION ?? OSM_ATTRIBUTION,
      defaultBbox,
      rtlPluginUrl,
    };
  }
  if (requested === "osm-raster") {
    return {
      provider: "osm-raster",
      style: osmRasterStyle(),
      attribution: OSM_ATTRIBUTION,
      defaultBbox,
      rtlPluginUrl: null, // raster tiles have no client-rendered labels
    };
  }
  return {
    provider: "openfreemap",
    style: OPENFREEMAP_STYLE,
    attribution: "OpenFreeMap © OpenMapTiles, data © OpenStreetMap contributors",
    defaultBbox,
    rtlPluginUrl,
  };
}
