"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type {
  GeoJSONSource,
  LngLatBoundsLike,
  Map as MapLibreMap,
  MapGeoJSONFeature,
  MapMouseEvent,
  Marker as MapLibreMarker,
} from "maplibre-gl";
import { type RefObject, useEffect, useLayoutEffect, useRef, useState } from "react";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { parseHex, tagLabel } from "@/lib/map/bubbles";
import {
  cameraDuration,
  easeStandard,
  focusZoom,
  openAreaOffset,
  placeTagsBalanced,
  type TagBox,
} from "@/lib/map/camera";
import { type Bbox, closedRing, type LonLat, readBboxProperty } from "@/lib/map/geo";
import type { MapConfig } from "@/lib/map/provider";
import { extrusionColor, styleFor } from "@/lib/map/style";
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
  /** Opening view: once data arrives, frame the listings that fall inside
   * `initialBbox` (the launch area) instead of the whole configured box. */
  fitToData?: boolean;
}

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
/** From this zoom (about a district) listings are drawn as price tags. */
const BUBBLE_MIN_ZOOM = 10.5;
/** At most this many tags at once; the rest are marked by their dot. */
const TAG_LIMIT = 140;
/** Tag geometry (px): height, and how far its body sits above the spot. */
const TAG_H = 28;
const TAG_RISE = 8;
/** Balanced placement: grid cell, and the reach for counting hidden neighbours. */
const TAG_CELL = 150;
const TAG_ABSORB = 64;
/** The selected listing's ground halo, by zoom. */
const SELECTION_RADIUS = ["interpolate", ["linear"], ["zoom"], 11, 16, 17, 30];

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
  // Groups: the price tags' material (limestone on the night chart, white on
  // the limestone plate) with a cyan rim and a soft halo sized by count, so a
  // group reads as "several tags here".
  const tagBg = dark ? "#efe9de" : "#ffffff";
  const tagInk = dark ? "#0b0f17" : ink;
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
        "circle-opacity": 0.16,
        "circle-blur": 0.35,
        "circle-radius": ["step", countOf, 24, 10, 29, 50, 35, 200, 42] as never,
      },
    });
    map.addLayer({
      id: `clusters${suffix}`,
      type: "circle",
      source,
      ...range,
      filter: ["has", "point_count"],
      paint: {
        "circle-color": tagBg,
        "circle-stroke-color": spatial,
        "circle-stroke-width": 2,
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
      paint: { "text-color": tagInk },
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
      "circle-radius": SELECTION_RADIUS as never,
      "circle-stroke-color": cssVar("--accent-fill") || "#14b07f",
      "circle-stroke-opacity": 0.55,
      "circle-stroke-width": 1,
    },
  });
  // The exact spot of every listing (the tag's tail points at it); approximate
  // locations are hollow rings.
  const approx = ["boolean", ["get", "approximate"], false];
  map.addLayer({
    id: "points-area",
    type: "circle",
    source: "properties",
    minzoom: BUBBLE_MIN_ZOOM,
    filter: ["all", ["!", ["has", "point_count"]], approx] as never,
    paint: {
      "circle-color": spatial,
      "circle-opacity": 0.14,
      "circle-radius": ["interpolate", ["exponential", 1.6], ["zoom"], 11, 7, 15, 16, 18, 40],
      "circle-stroke-color": spatial,
      "circle-stroke-opacity": 0.35,
      "circle-stroke-width": 1,
    },
  });
  map.addLayer({
    id: "points-under",
    type: "circle",
    source: "properties",
    minzoom: BUBBLE_MIN_ZOOM,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": spatial,
      "circle-radius": ["case", approx, 2.5, 3.5] as never,
      "circle-stroke-color": canvas,
      "circle-stroke-width": 1.5,
    },
  });

  // Price tags are HTML, so the map's label engine cannot see them. These
  // invisible symbols (one per drawn tag, the tag's size) sit on top of every
  // layer: placed first, they make overlapping district and road names step
  // aside — prices win over street labels; the river and city names, placed
  // where no tag is, stay.
  if (!map.hasImage("tag-block")) {
    map.addImage("tag-block", { width: 1, height: 1, data: new Uint8Array(4) });
  }
  map.addSource("tag-blockers", { type: "geojson", data: EMPTY });
  map.addLayer({
    id: "tag-blockers",
    type: "symbol",
    source: "tag-blockers",
    layout: {
      "text-field": ["get", "label"],
      "text-font": ["Noto Sans Bold"],
      "text-size": 13,
      "text-anchor": "bottom",
      "text-offset": [0, -1],
      "text-allow-overlap": true,
      "text-ignore-placement": false,
      "icon-image": "tag-block",
      "icon-text-fit": "both",
      "icon-text-fit-padding": [8, 14, 8, 14],
      "icon-allow-overlap": true,
      "icon-ignore-placement": false,
    },
    paint: { "text-opacity": 0, "icon-opacity": 0 },
  });
}

interface Tag {
  marker: MapLibreMarker;
  el: HTMLDivElement;
  button: HTMLButtonElement;
  value: HTMLSpanElement;
  badge: HTMLSpanElement;
  width: number;
  coords: [number, number];
  label: string;
  leaving?: ReturnType<typeof setTimeout>;
}

interface TagState {
  features: Feature[];
  selectedId: string | null;
  highlightId: string | null;
  locale: Locale;
}

/**
 * The HTML price tags over the map, keyed by listing id. Tags are placed when
 * the camera settles (they ride with the map while it moves), without overlap;
 * a tag that does not fit leaves its listing marked by the dot below.
 */
class PriceTags {
  private tags = new Map<string, Tag>();

  constructor(
    private map: MapLibreMap,
    private Marker: typeof MapLibreMarker,
    private onPick: (id: string) => void,
  ) {}

  /** Tags shown (not leaving). */
  get count(): number {
    let n = 0;
    for (const tag of this.tags.values()) if (!tag.leaving) n++;
    return n;
  }

  sync({ features, selectedId, highlightId, locale }: TagState): number {
    const map = this.map;
    const show = map.getZoom() >= BUBBLE_MIN_ZOOM;
    const canvas = map.getCanvas();
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const boxes: TagBox[] = [];
    const byId = new Map<string, Feature>();
    if (show) {
      for (const f of features) {
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
        const width = this.tags.get(id)?.width || label.length * 7.4 + 22;
        byId.set(id, f);
        boxes.push({
          id,
          x: at.x - width / 2,
          y: at.y - TAG_RISE - TAG_H,
          width,
          height: TAG_H,
          pinned: id === selectedId || id === highlightId,
        });
      }
    }
    // Balanced: one tag per screen cell first, so prices cover the whole view;
    // a listing without room is counted on its nearest tag ("+N").
    const { shown: visible, more } = placeTagsBalanced(boxes, TAG_LIMIT, {
      gap: 6,
      cell: TAG_CELL,
      absorb: TAG_ABSORB,
    });
    // Departures: fade out, then remove.
    for (const [id, tag] of this.tags) {
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
          this.tags.delete(id);
        },
        reducedMotion() ? 0 : 160,
      );
    }
    // Arrivals and state.
    for (const id of visible) {
      const f = byId.get(id)!;
      const p = (f.properties ?? {}) as Record<string, unknown>;
      const coords = (f.geometry as Point).coordinates as [number, number];
      const label = tagLabel(p.price_amount, p.currency, p.price_on_request, p.rent_period, locale);
      let tag = this.tags.get(id);
      if (!tag) {
        const el = document.createElement("div");
        el.className = "map-tag-anchor";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "map-tag";
        const value = document.createElement("span");
        const badge = document.createElement("span");
        badge.className = "map-tag-more";
        button.append(value, badge);
        // Keyboard and screen-reader users choose listings from the results
        // list ("Show on map"); the tags are a pointer shortcut to the same.
        button.tabIndex = -1;
        button.setAttribute("aria-hidden", "true");
        el.appendChild(button);
        button.addEventListener("click", () => this.onPick(id));
        const marker = new this.Marker({ element: el, anchor: "bottom", offset: [0, -TAG_RISE] })
          .setLngLat(coords)
          .addTo(map);
        tag = { marker, el, button, value, badge, width: 0, coords, label };
        this.tags.set(id, tag);
      } else {
        tag.marker.setLngLat(coords);
        tag.coords = coords;
        tag.label = label;
      }
      if (tag.value.textContent !== label) tag.value.textContent = label;
      const extra = more.get(id) ?? 0;
      const badgeText = extra > 0 ? `+${extra}` : "";
      if (tag.badge.textContent !== badgeText) tag.badge.textContent = badgeText;
      if (extra > 0) tag.button.dataset.more = String(extra);
      else delete tag.button.dataset.more;
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
    return visible.size;
  }

  /**
   * Invisible stand-ins for the drawn tags in the map's own label collision:
   * basemap labels (districts, roads) yield to a price where they would meet.
   */
  blockers(): FeatureCollection {
    const features: Feature[] = [];
    for (const tag of this.tags.values()) {
      if (tag.leaving) continue;
      features.push({
        type: "Feature",
        properties: { label: tag.label },
        geometry: { type: "Point", coordinates: tag.coords },
      });
    }
    return { type: "FeatureCollection", features };
  }

  destroy(): void {
    for (const tag of this.tags.values()) {
      if (tag.leaving) clearTimeout(tag.leaving);
      tag.marker.remove();
    }
    this.tags.clear();
  }
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
  // The listings the HTML price tags are drawn from (tags: see PriceTags).
  const points = useRef<Feature[]>([]);
  const syncRef = useRef<() => void>(() => undefined);
  const focusRef = useRef<(coords: [number, number]) => void>(() => undefined);
  const fitRef = useRef<(bbox: Bbox) => void>(() => undefined);
  const fitted = useRef(false);

  // Create the map once; overlays are (re)installed on every style load.
  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    let dark = false;
    const cleanups: (() => void)[] = [];
    let priceTags: PriceTags | null = null;
    (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (cancelled || !container.current) return;
        // Served by the site itself: the bundler does not ship MapLibre 6's worker.
        maplibre.setWorkerUrl(maplibreWorkerUrl(maplibre.getVersion()));
        // No RTL text plugin: MapLibre 6 shapes Arabic labels natively.
        const { config } = latest.current;
        dark = isDark();
        map = new maplibre.Map({
          container: container.current,
          style: styleFor(config, dark, latest.current.locale),
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
        // Price tags: HTML, so prices are set in the site's fonts (proper
        // Arabic), and selection, hover, arrival and departure are CSS.
        const tagLayer = new PriceTags(map, maplibre.Marker, (id) => {
          if (latest.current.drawing !== null) return;
          const feature = points.current.find((f) => String((f.properties ?? {}).id) === id);
          if (!feature) return;
          latest.current.onSelect(id, (feature.properties ?? {}) as Record<string, unknown>);
          focusRef.current((feature.geometry as Point).coordinates as [number, number]);
        });
        priceTags = tagLayer;
        syncRef.current = () => {
          const shown = tagLayer.sync({
            features: points.current,
            selectedId: latest.current.selectedId ?? null,
            highlightId: latest.current.highlightId,
            locale: latest.current.locale,
          });
          if (container.current) container.current.dataset.bubbles = String(shown);
          (map?.getSource("tag-blockers") as GeoJSONSource | undefined)?.setData(
            tagLayer.blockers(),
          );
        };
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
          installOverlays(map, latest.current.config);
          setStyleVersion((v) => v + 1);
          setReady(true);
        });

        // Follow the site theme (toggle or system change) with the matching basemap.
        const onTheme = () => {
          const next = isDark();
          if (!map || next === dark) return;
          if (config.provider !== "openfreemap" && !config.darkStyle) return;
          dark = next;
          // A full reload (no diff), so `style.load` fires and our overlays return.
          map.setStyle(styleFor(config, dark, latest.current.locale), { diff: false });
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
          // Tablets and up dock the results rail; wide screens also stand the
          // preview card at the bottom of the start side.
          const docked = window.matchMedia("(min-width: 768px)").matches;
          const wide = window.matchMedia("(min-width: 1024px)").matches;
          const rail = document.querySelector<HTMLElement>("[data-map-rail]");
          const railWidth = docked && rail ? rail.getBoundingClientRect().width : 0;
          return { railWidth, bottom: wide ? 160 : docked ? 160 : 240, wide };
        };
        const padding = (base: number) => {
          const { railWidth } = cover();
          const start = base + railWidth;
          return rtl()
            ? { top: base, bottom: base, left: base, right: start }
            : { top: base, bottom: base, left: start, right: base };
        };

        // The opening view settles on the listings themselves (never zooming
        // past street scale), beside the results rail.
        fitRef.current = (b) => {
          if (!map) return;
          map.fitBounds(
            [
              [b[0], b[1]],
              [b[2], b[3]],
            ],
            {
              padding: padding(64),
              maxZoom: 14,
              duration: cameraDuration(reducedMotion(), 900),
              easing: easeStandard,
            },
          );
        };

        // Selecting a listing glides to it: at most two zoom levels, bearing
        // untouched, centred in the open part of the map.
        focusRef.current = (coords) => {
          if (!map) return;
          const { railWidth, bottom, wide } = cover();
          // Respect the reader's framing: a listing already well inside the
          // open part of the map, close enough to read, is not moved to.
          const at = map.project(coords);
          const w = map.getCanvas().clientWidth;
          const h = map.getCanvas().clientHeight;
          const startEdge = rtl() ? w - railWidth : railWidth;
          const inX = rtl()
            ? at.x > 56 && at.x < startEdge - 56
            : at.x > startEdge + 56 && at.x < w - 56;
          // On wide screens the preview card stands at the bottom of the start side.
          const fromStart = rtl() ? startEdge - at.x : at.x - startEdge;
          const underCard = wide && fromStart < 420 && at.y > h - 480;
          if (inX && !underCard && at.y > 96 && at.y < h - bottom - 48 && map.getZoom() >= 13) {
            return;
          }
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
          container.current.dataset.bubbles = String(tagLayer.count);
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
      priceTags?.destroy();
      syncRef.current = () => undefined;
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  // Data updates (re-applied after every style load).
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const data = (props.data as FeatureCollection | null) ?? EMPTY;
    points.current = data.features;
    if (props.fitToData && !fitted.current && data.features.length > 0) {
      fitted.current = true;
      const [w0, s0, e0, n0] = props.initialBbox;
      const inside = data.features
        .filter((f) => f.geometry.type === "Point")
        .map((f) => (f.geometry as Point).coordinates as [number, number])
        .filter(([lon, lat]) => lon >= w0 && lon <= e0 && lat >= s0 && lat <= n0);
      if (inside.length > 1) {
        const lons = inside.map((c) => c[0]);
        const lats = inside.map((c) => c[1]);
        fitRef.current([
          Math.min(...lons),
          Math.min(...lats),
          Math.max(...lons),
          Math.max(...lats),
        ]);
      }
    }
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

  // A new selection marks its ground: the halo opens from the spot once.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !props.selectedId || !map.getLayer("selection-halo")) return;
    const d = reducedMotion() ? 0 : 650;
    map.setPaintProperty("selection-halo", "circle-radius-transition", { duration: 0, delay: 0 });
    map.setPaintProperty("selection-halo", "circle-radius", 2);
    map.setPaintProperty("selection-halo", "circle-opacity-transition", { duration: 0, delay: 0 });
    map.setPaintProperty("selection-halo", "circle-opacity", 0.4);
    const frame = requestAnimationFrame(() => {
      if (!map.getLayer("selection-halo")) return;
      map.setPaintProperty("selection-halo", "circle-radius-transition", { duration: d, delay: 0 });
      map.setPaintProperty("selection-halo", "circle-radius", SELECTION_RADIUS as never);
      map.setPaintProperty("selection-halo", "circle-opacity-transition", {
        duration: d,
        delay: 0,
      });
      map.setPaintProperty("selection-halo", "circle-opacity", 0.16);
    });
    return () => cancelAnimationFrame(frame);
  }, [ready, styleVersion, props.selectedId]);

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
            minzoom: 13,
            paint: {
              "fill-extrusion-color": extrusionColor(isDark()),
              "fill-extrusion-vertical-gradient": true,
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
    // Turning 3D on also brings buildings into view (at most two zoom levels).
    const pitch = on ? 50 : 0;
    const zoom = on && map.getZoom() < 14 ? Math.min(map.getZoom() + 2, 15) : map.getZoom();
    if (Math.abs(map.getPitch() - pitch) > 0.5 || zoom !== map.getZoom()) {
      map.easeTo({
        pitch,
        zoom,
        duration: cameraDuration(reducedMotion(), 900),
        easing: easeStandard,
      });
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
