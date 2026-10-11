"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type {
  GeoJSONSource,
  LngLatBoundsLike,
  Map as MapLibreMap,
  MapGeoJSONFeature,
  MapMouseEvent,
  Marker as MapLibreMarker,
  StyleSpecification,
} from "maplibre-gl";
import { type RefObject, useEffect, useLayoutEffect, useRef, useState } from "react";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { type LayerInfo, applyBasemapTone } from "@/lib/map/basemap";
import { parseHex, tagLabel } from "@/lib/map/bubbles";
import {
  cameraDuration,
  easeStandard,
  focusZoom,
  openAreaOffset,
  placeTags,
  type TagBox,
} from "@/lib/map/camera";
import { type Bbox, closedRing, type LonLat, readBboxProperty } from "@/lib/map/geo";
import type { MapConfig } from "@/lib/map/provider";
import { maplibreWorkerUrl } from "@/lib/map/worker";
import type { Feature, FeatureCollection, Point } from "geojson";

export interface MapFeatureCollection {
  type: "FeatureCollection";
  features: Feature[];
  meta?: { mode: "points" | "clusters"; total: number; limit: number };
}

/** A request to select a listing and glide to it (from the results list). */
export interface FocusRequest {
  id: string;
  lon: number;
  lat: number;
  /** Changes on every request, so asking twice for the same listing still moves. */
  n: number;
}

export interface PropertyMapProps {
  config: MapConfig;
  dict: Dictionary;
  locale: Locale;
  initialBbox: Bbox;
  data: MapFeatureCollection | null;
  boundaries: FeatureCollection | null;
  showBoundaries?: boolean;
  pois?: FeatureCollection | null;
  /** "Future Iraq" development projects (with provenance in their properties). */
  development?: FeatureCollection | null;
  onSelectProject?: (properties: Record<string, unknown> | null) => void;
  satellite?: boolean;
  /** Extruded buildings from OpenStreetMap heights, with a pitched camera. */
  buildings3d?: boolean;
  polygon: LonLat[] | null;
  drawing: LonLat[] | null;
  /** The listing open in the selection card (emerald tag, halo on the map). */
  selectedId?: string | null;
  /** The listing under the pointer in the results list (outlined tag). */
  highlightId: string | null;
  focusRequest?: FocusRequest | null;
  /** Fly to these bounds when they change (e.g. "near me"). */
  focusBbox?: Bbox | null;
  onViewportChange: (bbox: Bbox, zoom: number) => void;
  onSelect: (id: string | null, properties?: Record<string, unknown>) => void;
  onDrawPoint: (point: LonLat) => void;
  /** Edge-to-edge (map-first stage): no rounded frame, no minimum height. */
  bleed?: boolean;
}

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
/** From this zoom (about a district) listings are drawn as price tags. */
const BUBBLE_MIN_ZOOM = 10.5;
/** At most this many tags at once; the rest are marked by their dot. */
const TAG_LIMIT = 140;

/** POI colours by category family (also used by the layers panel legend). */
export const POI_COLORS: Record<string, string> = {
  SCHOOL: "#5b8def",
  UNIVERSITY: "#5b8def",
  HOSPITAL: "#e8665a",
  CLINIC: "#e8665a",
  PHARMACY: "#e8665a",
  MOSQUE: "#3fa58f",
  CHURCH: "#3fa58f",
  MARKET: "#d29a3c",
  MALL: "#d29a3c",
  PARK: "#5aa964",
};

/** Layers that fade in and out when their overlay is switched (property → target). */
const FADES: Record<string, [string, unknown][]> = {
  "poi-dots": [
    ["circle-opacity", ["case", ["boolean", ["get", "is_demo"], false], 0.55, 0.95]],
    ["circle-stroke-opacity", 1],
  ],
  "poi-labels": [["text-opacity", 1]],
  "development-area": [
    ["circle-opacity", 0.14],
    ["circle-stroke-opacity", 0.5],
  ],
  "development-points": [
    ["circle-opacity", 1],
    ["circle-stroke-opacity", 1],
  ],
  "development-labels": [["text-opacity", 1]],
  "boundary-fill": [["fill-opacity", 0.05]],
  "boundary-line": [["line-opacity", 0.8]],
};
const FADE_GROUPS = {
  pois: ["poi-dots", "poi-labels"],
  development: ["development-area", "development-points", "development-labels"],
  boundaries: ["boundary-fill", "boundary-line"],
} as const;
const FADE_MS = 280;

function isDark(): boolean {
  const forced = document.documentElement.dataset.theme;
  if (forced) return forced === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function styleFor(config: MapConfig, dark: boolean): string | StyleSpecification {
  return ((dark && config.darkStyle) || config.style) as string | StyleSpecification;
}

/** Fade a group of layers to visible (`on`) or to zero. */
function fadeLayers(map: MapLibreMap, layers: readonly string[], on: boolean, instant = false) {
  const duration = instant || reducedMotion() ? 0 : FADE_MS;
  for (const id of layers) {
    if (!map.getLayer(id)) continue;
    for (const [prop, target] of FADES[id] ?? []) {
      try {
        map.setPaintProperty(id, `${prop}-transition` as never, { duration, delay: 0 } as never);
        map.setPaintProperty(id, prop as never, (on ? target : 0) as never);
      } catch {
        // A property this layer type does not have: skip.
      }
    }
  }
}

/**
 * Our sources and layers on top of the basemap. Called on every `style.load`,
 * because switching the basemap (theme) removes them. Price tags are HTML
 * markers (see PropertyMap), so they survive style switches untouched.
 */
function installOverlays(map: MapLibreMap, config: MapConfig): void {
  const dark = isDark();
  const ink = cssVar("--ink") || (dark ? "#edeeef" : "#0e1114");
  const canvas = cssVar("--canvas") || (dark ? "#0a0c0f" : "#f2f3f1");
  const raised = cssVar("--surface-raised") || (dark ? "#181c21" : "#ffffff");
  const spatialRgba = parseHex(cssVar("--spatial-fill"), [20, 180, 204, 255]);
  const spatial = `rgb(${spatialRgba[0]} ${spatialRgba[1]} ${spatialRgba[2]})`;
  const gold = cssVar("--gold-fill") || "#c49640";

  // Satellite imagery sits under the basemap's labels when configured.
  if (config.satellite && !map.getSource("satellite")) {
    map.addSource("satellite", {
      type: "raster",
      tiles: [config.satellite.tiles],
      tileSize: 256,
      attribution: config.satellite.attribution,
    });
    const firstSymbol = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
    map.addLayer(
      {
        id: "satellite",
        type: "raster",
        source: "satellite",
        layout: { visibility: "none" },
        paint: { "raster-opacity-transition": { duration: FADE_MS, delay: 0 } },
      },
      firstSymbol,
    );
  }

  // Two views of the same listings: grouped circles for country/region zoom and
  // individual points (dots under the HTML price tags) from district zoom.
  map.addSource("properties", { type: "geojson", data: EMPTY, promoteId: "id" });
  map.addSource("properties-grouped", {
    type: "geojson",
    data: EMPTY,
    cluster: true,
    clusterRadius: 44,
    clusterMaxZoom: 22,
    clusterProperties: { total: ["+", ["coalesce", ["get", "point_count"], 1]] },
  });
  map.addSource("boundaries", { type: "geojson", data: EMPTY });
  map.addSource("area", { type: "geojson", data: EMPTY });
  map.addSource("pois", { type: "geojson", data: EMPTY });
  map.addSource("development", { type: "geojson", data: EMPTY, promoteId: "id" });

  // Area boundaries: a fine dashed survey line, barely tinted inside.
  map.addLayer({
    id: "boundary-fill",
    type: "fill",
    source: "boundaries",
    filter: ["==", ["geometry-type"], "Polygon"],
    paint: { "fill-color": spatial, "fill-opacity": 0.05 },
  });
  map.addLayer({
    id: "boundary-line",
    type: "line",
    source: "boundaries",
    paint: {
      "line-color": spatial,
      "line-opacity": 0.8,
      "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.8, 14, 1.6] as never,
      "line-dasharray": [3, 2],
    },
  });

  // Drawn area: cyan (a place), dashed while drawing, solid once complete.
  map.addLayer({
    id: "area-fill",
    type: "fill",
    source: "area",
    filter: ["==", ["geometry-type"], "Polygon"],
    paint: { "fill-color": spatial, "fill-opacity": 0.08 },
  });
  map.addLayer({
    id: "area-line",
    type: "line",
    source: "area",
    filter: ["!=", ["geometry-type"], "Point"],
    layout: { "line-join": "round", "line-cap": "round" },
    paint: { "line-color": spatial, "line-width": 2 },
  });
  map.addLayer({
    id: "area-vertices",
    type: "circle",
    source: "area",
    filter: ["all", ["==", ["geometry-type"], "Point"], ["!", ["has", "cursor"]]],
    paint: {
      "circle-radius": ["case", ["boolean", ["get", "first"], false], 6.5, 4.5] as never,
      "circle-color": canvas,
      "circle-stroke-color": spatial,
      "circle-stroke-width": 2,
    },
  });

  // Places: small coloured dots, names from zoom 15.
  map.addLayer({
    id: "poi-dots",
    type: "circle",
    source: "pois",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 3, 16, 5.5],
      "circle-color": [
        "match",
        ["get", "category"],
        ...Object.entries(POI_COLORS).flat(),
        "#7c858e",
      ] as unknown as string,
      "circle-stroke-color": canvas,
      "circle-stroke-width": 1.5,
      "circle-opacity": 0,
      "circle-stroke-opacity": 0,
    },
  });
  map.addLayer({
    id: "poi-labels",
    type: "symbol",
    source: "pois",
    minzoom: 15,
    layout: {
      "text-field": ["get", "label"],
      "text-size": 11,
      "text-font": ["Noto Sans Regular"],
      "text-offset": [0, 1.1],
      "text-anchor": "top",
      "text-optional": true,
    },
    paint: {
      "text-color": ink,
      "text-halo-color": canvas,
      "text-halo-width": 1.2,
      "text-opacity": 0,
    },
  });

  // Future Iraq: gold (planned, not built). Area-level positions get a soft
  // disc so they never read as an exact site.
  map.addLayer({
    id: "development-area",
    type: "circle",
    source: "development",
    filter: ["!=", ["get", "location_precision"], "EXACT"],
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 10, 14, 40],
      "circle-color": gold,
      "circle-opacity": 0,
      "circle-stroke-color": gold,
      "circle-stroke-opacity": 0,
      "circle-stroke-width": 1,
    },
  });
  map.addLayer({
    id: "development-points",
    type: "circle",
    source: "development",
    paint: {
      "circle-radius": 6.5,
      "circle-color": gold,
      "circle-stroke-color": canvas,
      "circle-stroke-width": 2.5,
      "circle-opacity": 0,
      "circle-stroke-opacity": 0,
    },
  });
  map.addLayer({
    id: "development-labels",
    type: "symbol",
    source: "development",
    minzoom: 8,
    layout: {
      "text-field": ["get", "label"],
      "text-size": 11.5,
      "text-font": ["Noto Sans Bold"],
      "text-offset": [0, 1.2],
      "text-anchor": "top",
      "text-optional": true,
      "text-max-width": 10,
    },
    paint: {
      "text-color": cssVar("--gold") || "#ddb15e",
      "text-halo-color": canvas,
      "text-halo-width": 1.4,
      "text-opacity": 0,
    },
  });

  const countOf = ["coalesce", ["get", "total"], ["get", "point_count"]];
  // Groups: a raised disc with a cyan rim and the count in ink — the same
  // material as the price tags, so a group reads as "several tags here".
  for (const [suffix, source, range] of [
    ["", "properties-grouped", { maxzoom: BUBBLE_MIN_ZOOM }],
    ["-server", "properties", { minzoom: BUBBLE_MIN_ZOOM }],
  ] as const) {
    map.addLayer({
      id: `clusters-halo${suffix}`,
      type: "circle",
      source,
      ...range,
      filter: ["has", "point_count"],
      paint: {
        "circle-color": spatial,
        "circle-opacity": 0.12,
        "circle-radius": ["step", countOf, 22, 10, 26, 50, 31, 200, 37] as never,
      },
    });
    map.addLayer({
      id: `clusters${suffix}`,
      type: "circle",
      source,
      ...range,
      filter: ["has", "point_count"],
      paint: {
        "circle-color": raised,
        "circle-stroke-color": spatial,
        "circle-stroke-width": 1.5,
        "circle-radius": ["step", countOf, 15, 10, 18, 50, 22, 200, 27] as never,
      },
    });
    map.addLayer({
      id: `cluster-count${suffix}`,
      type: "symbol",
      source,
      ...range,
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["to-string", countOf] as never,
        "text-size": 12.5,
        "text-font": ["Noto Sans Bold"],
        "text-allow-overlap": true,
      },
      paint: { "text-color": ink },
    });
  }
  // Single listings below tag zoom: small cyan dots (prices appear when zooming in).
  map.addLayer({
    id: "points-dots",
    type: "circle",
    source: "properties-grouped",
    maxzoom: BUBBLE_MIN_ZOOM,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": spatial,
      "circle-radius": 5,
      "circle-stroke-color": canvas,
      "circle-stroke-width": 2,
    },
  });
  // Selection halo: a soft geographic highlight under the chosen listing.
  map.addLayer({
    id: "selection-halo",
    type: "circle",
    source: "properties",
    minzoom: BUBBLE_MIN_ZOOM,
    filter: ["==", ["get", "id"], ""],
    paint: {
      "circle-color": cssVar("--accent-fill") || "#14b07f",
      "circle-opacity": 0.16,
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 14, 17, 26],
      "circle-stroke-color": cssVar("--accent-fill") || "#14b07f",
      "circle-stroke-opacity": 0.55,
      "circle-stroke-width": 1,
    },
  });
  // The exact spot of every listing (the tag's tail points at it); approximate
  // locations are hollow rings.
  map.addLayer({
    id: "points-under",
    type: "circle",
    source: "properties",
    minzoom: BUBBLE_MIN_ZOOM,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": [
        "case",
        ["boolean", ["get", "approximate"], false],
        canvas,
        spatial,
      ] as never,
      "circle-radius": 3.5,
      "circle-stroke-color": [
        "case",
        ["boolean", ["get", "approximate"], false],
        spatial,
        canvas,
      ] as never,
      "circle-stroke-width": 1.5,
    },
  });
}

interface Tag {
  marker: MapLibreMarker;
  el: HTMLDivElement;
  button: HTMLButtonElement;
  width: number;
  leaving?: ReturnType<typeof setTimeout>;
}

export function PropertyMap(props: PropertyMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  // Latest props for MapLibre's event handlers; updated after each commit (before
  // any effect below or any later map event reads it).
  const latest = useRef(props);
  useLayoutEffect(() => {
    latest.current = props;
  });
  const [ready, setReady] = useState(false);
  const [styleVersion, setStyleVersion] = useState(0);
  const [failed, setFailed] = useState(false);
  // HTML price tags, keyed by listing id, and the listings they are drawn from.
  const tags = useRef(new Map<string, Tag>());
  const points = useRef<Feature[]>([]);
  const markerClass = useRef<typeof MapLibreMarker | null>(null);
  const syncRef = useRef<() => void>(() => undefined);
  const focusRef = useRef<(coords: [number, number]) => void>(() => undefined);

  // Create the map once; overlays are (re)installed on every style load.
  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    let dark = false;
    const cleanups: (() => void)[] = [];
    const tagMap = tags.current;
    (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (cancelled || !container.current) return;
        // Served by the site itself: the bundler does not ship MapLibre 6's worker.
        maplibre.setWorkerUrl(maplibreWorkerUrl(maplibre.getVersion()));
        markerClass.current = maplibre.Marker;
        // No RTL text plugin: MapLibre 6 shapes Arabic labels natively.
        const { config } = latest.current;
        dark = isDark();
        map = new maplibre.Map({
          container: container.current,
          style: styleFor(config, dark),
          bounds: latest.current.initialBbox as LngLatBoundsLike,
          fitBoundsOptions: { padding: 24 },
          attributionControl: {
            compact: true,
            // OpenFreeMap styles carry their own credits; avoid printing them twice.
            customAttribution: config.provider === "openfreemap" ? undefined : config.attribution,
          },
          maxZoom: 19,
          maxPitch: 60,
          // North stays up: bearing never changes, so the city never spins.
          dragRotate: false,
          pitchWithRotate: false,
        });
        map.touchZoomRotate.disableRotation();
        map.keyboard.disableRotation();
        map.touchPitch.disable();
        mapRef.current = map;
        // Zoom buttons at the bottom of the end side (wide screens; phones pinch).
        map.addControl(
          new maplibre.NavigationControl({ showCompass: false }),
          document.documentElement.dir === "rtl" ? "bottom-left" : "bottom-right",
        );
        // Errors must not crash the page; non-tile errors are logged for diagnosis.
        map.on("error", (e) => {
          const message = e.error?.message ?? "";
          if (!/tile|fetch|load/i.test(message)) console.warn(`[map] ${message}`);
        });

        map.on("style.load", () => {
          if (!map) return;
          if (latest.current.config.provider === "openfreemap") {
            const m = map;
            applyBasemapTone(
              {
                setPaintProperty: (l, prop, v) => m.setPaintProperty(l, prop as never, v as never),
              },
              m.getStyle().layers as LayerInfo[],
              isDark(),
            );
          }
          installOverlays(map, latest.current.config);
          setStyleVersion((v) => v + 1);
          setReady(true);
        });

        // Follow the site theme (toggle or system change) with the matching basemap.
        const onTheme = () => {
          const next = isDark();
          if (!map || next === dark || !config.darkStyle) return;
          dark = next;
          map.setStyle(styleFor(config, dark));
        };
        const observer = new MutationObserver(onTheme);
        observer.observe(document.documentElement, { attributeFilter: ["data-theme"] });
        const media = window.matchMedia("(prefers-color-scheme: dark)");
        media.addEventListener("change", onTheme);
        cleanups.push(() => observer.disconnect());
        cleanups.push(() => media.removeEventListener("change", onTheme));

        const rtl = () => document.documentElement.dir === "rtl";
        /** Space covered by the results rail (wide screens) and a bottom card. */
        const cover = () => {
          const wide = window.matchMedia("(min-width: 1024px)").matches;
          const rail = document.querySelector<HTMLElement>("[data-map-rail]");
          const railWidth = wide && rail ? rail.getBoundingClientRect().width : 0;
          return { railWidth, bottom: wide ? 160 : 240 };
        };
        const padding = (base: number) => {
          const { railWidth } = cover();
          const start = base + railWidth;
          return rtl()
            ? { top: base, bottom: base, left: base, right: start }
            : { top: base, bottom: base, left: start, right: base };
        };

        // Selecting a listing glides to it: at most two zoom levels, bearing
        // untouched, centred in the open part of the map.
        focusRef.current = (coords) => {
          if (!map) return;
          const { railWidth, bottom } = cover();
          map.easeTo({
            center: coords,
            zoom: focusZoom(map.getZoom()),
            offset: openAreaOffset(railWidth, bottom, rtl()),
            duration: cameraDuration(reducedMotion()),
            easing: easeStandard,
          });
        };

        // While drawing, a click on any layer is a polygon vertex (the general
        // click handler below), never a zoom into a group.
        map.on("click", ["clusters-server", "points-dots"], (event: MapMouseEvent) => {
          if (latest.current.drawing !== null || !map) return;
          map.easeTo({
            center: event.lngLat,
            zoom: map.getZoom() + 2,
            duration: cameraDuration(reducedMotion(), 650),
            easing: easeStandard,
          });
        });
        map.on(
          "click",
          "clusters",
          async (event: MapMouseEvent & { features?: MapGeoJSONFeature[] }) => {
            const feature = event.features?.[0];
            if (!feature || !map || latest.current.drawing !== null) return;
            const serverBbox = readBboxProperty(feature.properties?.bbox);
            if (serverBbox) {
              map.fitBounds(serverBbox as LngLatBoundsLike, {
                padding: padding(56),
                maxZoom: 17,
                duration: cameraDuration(reducedMotion(), 700),
                easing: easeStandard,
              });
              return;
            }
            // A group opens to the zoom at which it splits (no further), and its
            // tags then arrive with their entrance motion.
            const source = map.getSource("properties-grouped") as GeoJSONSource;
            const zoom = await source.getClusterExpansionZoom(
              Number(feature.properties?.cluster_id),
            );
            const geometry = feature.geometry as Point;
            map.easeTo({
              center: geometry.coordinates as [number, number],
              zoom: Math.min(Math.max(zoom, map.getZoom() + 1), map.getZoom() + 3),
              duration: cameraDuration(reducedMotion(), 650),
              easing: easeStandard,
            });
          },
        );
        map.on(
          "click",
          "points-under",
          (event: MapMouseEvent & { features?: MapGeoJSONFeature[] }) => {
            const feature = event.features?.[0];
            if (!feature || !map || latest.current.drawing !== null) return;
            const p = (feature.properties ?? {}) as Record<string, unknown>;
            latest.current.onSelect(String(p.id), p);
            if (latest.current.bleed && feature.geometry.type === "Point") {
              focusRef.current((feature.geometry as Point).coordinates as [number, number]);
            }
          },
        );
        map.on(
          "click",
          "development-points",
          (event: MapMouseEvent & { features?: MapGeoJSONFeature[] }) => {
            const feature = event.features?.[0];
            if (!feature || latest.current.drawing !== null) return;
            latest.current.onSelectProject?.((feature.properties ?? {}) as Record<string, unknown>);
          },
        );
        map.on("click", (event: MapMouseEvent) => {
          // A click on a price tag is handled by the tag itself.
          const target = event.originalEvent?.target as Element | null;
          if (target?.closest?.(".map-tag")) return;
          if (latest.current.drawing !== null) {
            latest.current.onDrawPoint([event.lngLat.lng, event.lngLat.lat]);
            return;
          }
          const project = map?.queryRenderedFeatures(event.point, {
            layers: ["development-points"],
          });
          if (!project?.length) latest.current.onSelectProject?.(null);
          const hit = map?.queryRenderedFeatures(event.point, {
            layers: ["points-under", "clusters", "clusters-server", "points-dots"],
          });
          if (!hit?.length) latest.current.onSelect(null);
        });
        // While drawing, the outline follows the pointer from the last vertex.
        map.on("mousemove", (event: MapMouseEvent) => {
          const drawing = latest.current.drawing;
          if (!map || !drawing || drawing.length === 0) return;
          const cursor: LonLat = [event.lngLat.lng, event.lngLat.lat];
          (map.getSource("area") as GeoJSONSource | undefined)?.setData(
            areaFeatures(drawing, cursor),
          );
        });
        for (const layer of [
          "development-points",
          "clusters",
          "clusters-server",
          "points-dots",
          "points-under",
        ]) {
          map.on("mouseenter", layer, () => {
            if (map && latest.current.drawing === null) map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", layer, () => {
            if (map && latest.current.drawing === null) map.getCanvas().style.cursor = "";
          });
        }
        const report = () => {
          if (!map) return;
          const b = map.getBounds();
          latest.current.onViewportChange(
            [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
            Math.round(map.getZoom()),
          );
        };
        map.on("moveend", report);
        map.once("load", report);
        // Tags are re-placed when the camera settles (they ride with the map
        // while it moves, so nothing is recomputed per frame).
        map.on("moveend", () => syncRef.current());
        map.on("resize", () => syncRef.current());
        // Rendered counts for automated checks (and nothing else).
        map.on("idle", () => {
          if (!map || !container.current || !map.getLayer("points-under")) return;
          const count = (layers: string[]) => map!.queryRenderedFeatures({ layers }).length;
          container.current.dataset.bubbles = String(visibleTags(tagMap));
          container.current.dataset.clusters = String(count(["clusters", "clusters-server"]));
          container.current.dataset.pois = String(count(["poi-dots"]));
          container.current.dataset.projects = String(count(["development-points"]));
          container.current.dataset.zoom = map.getZoom().toFixed(2);
        });
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      cleanups.forEach((fn) => fn());
      for (const tag of tagMap.values()) {
        if (tag.leaving) clearTimeout(tag.leaving);
        tag.marker.remove();
      }
      tagMap.clear();
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  // Price tags: HTML, so prices are set in the site's fonts (proper Arabic),
  // and selection, hover, arrival and departure are CSS transitions.
  const syncTags = () => {
    const map = mapRef.current;
    const Marker = markerClass.current;
    if (!map || !Marker || !container.current) return;
    const { selectedId, highlightId, locale } = latest.current;
    const show = map.getZoom() >= BUBBLE_MIN_ZOOM;
    const canvas = map.getCanvas();
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const boxes: TagBox[] = [];
    const byId = new Map<string, Feature>();
    if (show) {
      for (const f of points.current) {
        const p = (f.properties ?? {}) as Record<string, unknown>;
        if ("point_count" in p || f.geometry.type !== "Point") continue;
        const id = String(p.id);
        const [lon, lat] = (f.geometry as Point).coordinates as [number, number];
        const at = map.project([lon, lat]);
        if (at.x < -80 || at.y < -40 || at.x > w + 80 || at.y > h + 40) continue;
        const label = tagLabel(
          p.price_amount,
          p.currency,
          p.price_on_request,
          p.rent_period,
          locale,
        );
        const width = tags.current.get(id)?.width || label.length * 7 + 20;
        byId.set(id, f);
        boxes.push({
          id,
          x: at.x - width / 2,
          y: at.y - 34,
          width,
          height: 26,
          pinned: id === selectedId || id === highlightId,
        });
      }
    }
    const visible = placeTags(boxes, TAG_LIMIT);
    // Departures: fade out, then remove.
    for (const [id, tag] of tags.current) {
      if (visible.has(id)) {
        if (tag.leaving) {
          clearTimeout(tag.leaving);
          tag.leaving = undefined;
          delete tag.el.dataset.leaving;
        }
        continue;
      }
      if (tag.leaving) continue;
      tag.el.dataset.leaving = "1";
      tag.leaving = setTimeout(
        () => {
          tag.marker.remove();
          tags.current.delete(id);
        },
        reducedMotion() ? 0 : 160,
      );
    }
    // Arrivals and state.
    for (const id of visible) {
      const f = byId.get(id)!;
      const p = (f.properties ?? {}) as Record<string, unknown>;
      const coords = (f.geometry as Point).coordinates as [number, number];
      let tag = tags.current.get(id);
      const label = tagLabel(p.price_amount, p.currency, p.price_on_request, p.rent_period, locale);
      if (!tag) {
        const el = document.createElement("div");
        el.className = "map-tag-anchor";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "map-tag";
        // Keyboard and screen-reader users choose listings from the results
        // list ("Show on map"); the tags are a pointer shortcut to the same.
        button.tabIndex = -1;
        button.setAttribute("aria-hidden", "true");
        el.appendChild(button);
        button.addEventListener("click", () => {
          if (latest.current.drawing !== null) return;
          const feature = byIdCurrent(points.current, id);
          if (!feature) return;
          latest.current.onSelect(id, (feature.properties ?? {}) as Record<string, unknown>);
          focusRef.current((feature.geometry as Point).coordinates as [number, number]);
        });
        const marker = new Marker({ element: el, anchor: "bottom", offset: [0, -7] })
          .setLngLat(coords)
          .addTo(map);
        tag = { marker, el, button, width: 0 };
        tags.current.set(id, tag);
      } else {
        tag.marker.setLngLat(coords);
      }
      if (tag.button.textContent !== label) tag.button.textContent = label;
      if (p.approximate === true) tag.button.dataset.approx = "1";
      else delete tag.button.dataset.approx;
      const state = id === selectedId ? "selected" : id === highlightId ? "hover" : "";
      if ((tag.button.dataset.state ?? "") !== state) {
        if (state) tag.button.dataset.state = state;
        else delete tag.button.dataset.state;
      }
      tag.el.style.zIndex = state === "selected" ? "3" : state === "hover" ? "2" : "1";
      if (!tag.width) tag.width = tag.button.offsetWidth || label.length * 7 + 20;
    }
    container.current.dataset.bubbles = String(visible.size);
  };
  useLayoutEffect(() => {
    syncRef.current = syncTags;
  });

  // Data updates (re-applied after every style load).
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const data = (props.data as FeatureCollection | null) ?? EMPTY;
    points.current = data.features;
    (map.getSource("properties") as GeoJSONSource | undefined)?.setData(data);
    (map.getSource("properties-grouped") as GeoJSONSource | undefined)?.setData(data);
    syncRef.current();
  }, [ready, styleVersion, props.data]);

  // Tag states follow selection, hover and language.
  useEffect(() => {
    if (!ready) return;
    syncRef.current();
    const map = mapRef.current;
    if (map?.getLayer("selection-halo")) {
      map.setFilter("selection-halo", [
        "all",
        ["!", ["has", "point_count"]],
        ["==", ["get", "id"], props.selectedId ?? ""],
      ]);
    }
  }, [ready, styleVersion, props.selectedId, props.highlightId, props.locale]);

  // Overlays fade in when switched on and fade out before their data is cleared.
  useFadedData(
    mapRef,
    ready,
    styleVersion,
    "boundaries",
    FADE_GROUPS.boundaries,
    (() => {
      const visible = props.showBoundaries ?? true;
      return visible ? (props.boundaries ?? null) : null;
    })(),
  );
  useFadedData(mapRef, ready, styleVersion, "pois", FADE_GROUPS.pois, props.pois ?? null);
  useFadedData(
    mapRef,
    ready,
    styleVersion,
    "development",
    FADE_GROUPS.development,
    props.development ?? null,
  );

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !map.getLayer("satellite")) return;
    if (props.satellite) {
      map.setLayoutProperty("satellite", "visibility", "visible");
      map.setPaintProperty("satellite", "raster-opacity", 0);
      requestAnimationFrame(() => map.setPaintProperty("satellite", "raster-opacity", 1));
    } else {
      map.setLayoutProperty("satellite", "visibility", "none");
    }
  }, [ready, styleVersion, props.satellite]);

  // 3D: real building footprints extruded to their OpenStreetMap heights
  // (OpenMapTiles' render_height), seen from a pitched camera. Off = flat, north up.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const on = !!props.buildings3d;
    const style = map.getStyle();
    const native = style.layers.some((l) => l.type === "fill-extrusion" && l.id !== "makan-3d");
    if (on && !native && !map.getLayer("makan-3d")) {
      const vector = Object.entries(style.sources).find(([, s]) => s.type === "vector")?.[0];
      if (vector) {
        const firstSymbol = style.layers.find((l) => l.type === "symbol")?.id;
        map.addLayer(
          {
            id: "makan-3d",
            type: "fill-extrusion",
            source: vector,
            "source-layer": "building",
            minzoom: 14,
            paint: {
              "fill-extrusion-color": isDark() ? "#1d2228" : "#dcdfdb",
              "fill-extrusion-height": ["coalesce", ["get", "render_height"], 0],
              "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
              "fill-extrusion-opacity": 0.88,
            },
          },
          firstSymbol,
        );
      }
    }
    if (map.getLayer("makan-3d")) {
      map.setLayoutProperty("makan-3d", "visibility", on ? "visible" : "none");
    }
    if (on) map.touchPitch.enable();
    else map.touchPitch.disable();
    const pitch = on ? 50 : 0;
    if (Math.abs(map.getPitch() - pitch) > 0.5) {
      map.easeTo({ pitch, duration: cameraDuration(reducedMotion(), 900), easing: easeStandard });
    }
  }, [ready, styleVersion, props.buildings3d]);

  // Drawing: entry (crosshair), active (vertices, dashed outline following the
  // pointer), complete (the area settles into a solid cyan outline).
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const drawing = props.drawing;
    const points = drawing ?? props.polygon ?? [];
    (map.getSource("area") as GeoJSONSource | undefined)?.setData(areaFeatures(points));
    if (container.current) container.current.dataset.drawing = drawing ? "1" : "0";
    map.getCanvas().style.cursor = drawing ? "crosshair" : "";
    if (map.getLayer("area-line")) {
      map.setPaintProperty("area-line", "line-dasharray", drawing ? [2, 1.5] : [1, 0]);
      if (!drawing && props.polygon) {
        const d = cameraDuration(reducedMotion(), 500);
        map.setPaintProperty("area-line", "line-width-transition", { duration: 0, delay: 0 });
        map.setPaintProperty("area-line", "line-width", 4);
        map.setPaintProperty("area-fill", "fill-opacity-transition", { duration: 0, delay: 0 });
        map.setPaintProperty("area-fill", "fill-opacity", 0);
        requestAnimationFrame(() => {
          if (!map.getLayer("area-line")) return;
          map.setPaintProperty("area-line", "line-width-transition", { duration: d, delay: 0 });
          map.setPaintProperty("area-line", "line-width", 2);
          map.setPaintProperty("area-fill", "fill-opacity-transition", { duration: d, delay: 0 });
          map.setPaintProperty("area-fill", "fill-opacity", 0.08);
        });
      }
    }
    // Quick clicks while drawing add points; they must not zoom the map.
    if (drawing) map.doubleClickZoom.disable();
    else map.doubleClickZoom.enable();
  }, [ready, styleVersion, props.drawing, props.polygon]);

  // The list asked to show a listing on the map.
  useEffect(() => {
    if (!ready || !props.focusRequest) return;
    focusRef.current([props.focusRequest.lon, props.focusRequest.lat]);
  }, [ready, props.focusRequest]);

  // Smooth camera to a requested area.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !props.focusBbox) return;
    map.fitBounds(props.focusBbox as LngLatBoundsLike, {
      padding: 48,
      duration: cameraDuration(reducedMotion(), 900),
      easing: easeStandard,
    });
  }, [ready, props.focusBbox]);

  return (
    <div
      className={`relative h-full w-full overflow-hidden bg-fill ${props.bleed ? "" : "min-h-[420px] rounded-[var(--radius-media)]"}`}
    >
      {/* Inline position: MapLibre adds .maplibregl-map { position: relative }, which
          overrides an `absolute` class and collapsed the map to 0px height. */}
      <div ref={container} style={{ position: "absolute", inset: 0 }} data-testid="map-canvas" />
      {!ready && !failed && (
        <div role="status" className="skeleton absolute inset-0 grid place-items-center">
          <p className="surface-float flex items-center gap-2 rounded-[var(--radius-control)] px-4 py-2 text-sm text-ink-2">
            <span aria-hidden className="size-2 animate-pulse rounded-full bg-spatial-fill" />
            {props.dict.map.loading}
          </p>
        </div>
      )}
      {failed && (
        <p role="alert" className="absolute inset-0 grid place-items-center text-sm text-danger">
          {props.dict.map.error}
        </p>
      )}
    </div>
  );
}

function byIdCurrent(features: Feature[], id: string): Feature | undefined {
  return features.find((f) => String((f.properties ?? {}).id) === id);
}

function visibleTags(tagMap: Map<string, Tag>): number {
  let n = 0;
  for (const tag of tagMap.values()) if (!tag.leaving) n++;
  return n;
}

/** Vertices (the first one larger), the outline and, from three points, the area. */
function areaFeatures(points: LonLat[], cursor?: LonLat): FeatureCollection {
  const features: Feature[] = points.map((coordinates, i) => ({
    type: "Feature",
    properties: i === 0 ? { first: true } : {},
    geometry: { type: "Point", coordinates },
  }));
  const path = cursor ? [...points, cursor] : points;
  if (path.length >= 3) {
    features.push({
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: [closedRing(path)] },
    });
  } else if (path.length === 2) {
    features.push({
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: path },
    });
  }
  return { type: "FeatureCollection", features };
}

/**
 * Sets a GeoJSON source and fades its layers: in when data arrives, out
 * (then cleared) when the overlay is switched off.
 */
function useFadedData(
  mapRef: RefObject<MapLibreMap | null>,
  ready: boolean,
  styleVersion: number,
  source: string,
  layers: readonly string[],
  data: FeatureCollection | null,
) {
  const shown = useRef(false);
  const lastStyle = useRef(-1);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const src = map.getSource(source) as GeoJSONSource | undefined;
    if (!src) return;
    const has = !!data && data.features.length > 0;
    if (has) {
      src.setData(data);
      // A fresh style starts at zero opacity: fade in (or stay visible).
      fadeLayers(map, layers, true, shown.current && styleVersion === lastStyle.current);
      shown.current = true;
      lastStyle.current = styleVersion;
      return;
    }
    if (!shown.current) {
      src.setData(EMPTY);
      return;
    }
    fadeLayers(map, layers, false);
    shown.current = false;
    const handle = setTimeout(
      () => (map.getSource(source) as GeoJSONSource | undefined)?.setData(EMPTY),
      reducedMotion() ? 0 : FADE_MS,
    );
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- layers/source are constants
  }, [ready, styleVersion, data]);
}
