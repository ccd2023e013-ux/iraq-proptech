"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type {
  GeoJSONSource,
  LngLatBoundsLike,
  Map as MapLibreMap,
  MapGeoJSONFeature,
  MapMouseEvent,
  StyleSpecification,
} from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { parseHex, pillImage, withPriceLabels } from "@/lib/map/bubbles";
import { type Bbox, closedRing, type LonLat, readBboxProperty } from "@/lib/map/geo";
import type { MapConfig } from "@/lib/map/provider";
import type { Feature, FeatureCollection, Point } from "geojson";

export interface MapFeatureCollection {
  type: "FeatureCollection";
  features: Feature[];
  meta?: { mode: "points" | "clusters"; total: number; limit: number };
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
  satellite?: boolean;
  polygon: LonLat[] | null;
  drawing: LonLat[] | null;
  highlightId: string | null;
  /** Fly to these bounds when they change (e.g. "near me"). */
  focusBbox?: Bbox | null;
  onViewportChange: (bbox: Bbox, zoom: number) => void;
  onSelect: (id: string | null, properties?: Record<string, unknown>) => void;
  onDrawPoint: (point: LonLat) => void;
}

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
let rtlPluginRequested = false;

/** POI colours by category family (also used by the layers panel legend). */
export const POI_COLORS: Record<string, string> = {
  SCHOOL: "#2563eb",
  UNIVERSITY: "#2563eb",
  HOSPITAL: "#dc2626",
  CLINIC: "#dc2626",
  PHARMACY: "#dc2626",
  MOSQUE: "#0f766e",
  CHURCH: "#0f766e",
  MARKET: "#b45309",
  MALL: "#b45309",
  PARK: "#15803d",
};

function isDark(): boolean {
  const forced = document.documentElement.dataset.theme;
  if (forced) return forced === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name);
}

function styleFor(config: MapConfig, dark: boolean): string | StyleSpecification {
  return ((dark && config.darkStyle) || config.style) as string | StyleSpecification;
}

/**
 * Our sources, images and layers on top of the basemap. Called on every
 * `style.load`, because switching the basemap (theme) removes them.
 */
function installOverlays(map: MapLibreMap, config: MapConfig): void {
  const surface = parseHex(cssVar("--surface"), [255, 255, 255, 255]);
  const ink = cssVar("--ink").trim() || "#10201e";
  const accent = parseHex(cssVar("--accent-fill"), [18, 116, 107, 255]);
  const hairline: [number, number, number, number] = isDark()
    ? [255, 255, 255, 60]
    : [16, 32, 30, 50];
  for (const [name, fill, stroke] of [
    ["bubble", surface, hairline],
    ["bubble-active", accent, accent],
  ] as const) {
    if (map.hasImage(name)) map.removeImage(name);
    const pill = pillImage(fill, stroke, 2);
    map.addImage(
      name,
      { width: pill.width, height: pill.height, data: pill.data },
      {
        pixelRatio: pill.pixelRatio,
        stretchX: pill.stretchX,
        stretchY: pill.stretchY,
        content: pill.content,
      },
    );
  }

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
      { id: "satellite", type: "raster", source: "satellite", layout: { visibility: "none" } },
      firstSymbol,
    );
  }

  map.addSource("properties", {
    type: "geojson",
    data: EMPTY,
    cluster: true,
    // Group only at country/region zoom; from city zoom every price is shown.
    clusterRadius: 40,
    clusterMaxZoom: 10,
    promoteId: "id",
    clusterProperties: { total: ["+", ["coalesce", ["get", "point_count"], 1]] },
  });
  map.addSource("boundaries", { type: "geojson", data: EMPTY });
  map.addSource("area", { type: "geojson", data: EMPTY });
  map.addSource("pois", { type: "geojson", data: EMPTY });

  map.addLayer({
    id: "boundary-fill",
    type: "fill",
    source: "boundaries",
    filter: ["==", ["geometry-type"], "Polygon"],
    paint: { "fill-color": "#2f7e78", "fill-opacity": 0.06 },
  });
  map.addLayer({
    id: "boundary-line",
    type: "line",
    source: "boundaries",
    paint: { "line-color": "#2f9e94", "line-width": 1.5, "line-dasharray": [2, 1] },
  });
  map.addLayer({
    id: "area-fill",
    type: "fill",
    source: "area",
    filter: ["==", ["geometry-type"], "Polygon"],
    paint: { "fill-color": "#c99a3a", "fill-opacity": 0.12 },
  });
  map.addLayer({
    id: "area-line",
    type: "line",
    source: "area",
    paint: { "line-color": "#b98a2c", "line-width": 2 },
  });
  map.addLayer({
    id: "area-vertices",
    type: "circle",
    source: "area",
    filter: ["==", ["geometry-type"], "Point"],
    paint: { "circle-radius": 4, "circle-color": "#b98a2c" },
  });

  // Places: small coloured dots, names from zoom 15.
  map.addLayer({
    id: "poi-dots",
    type: "circle",
    source: "pois",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 3, 16, 6],
      "circle-color": [
        "match",
        ["get", "category"],
        ...Object.entries(POI_COLORS).flat(),
        "#6b7a77",
      ] as unknown as string,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 1.5,
      "circle-opacity": ["case", ["boolean", ["get", "is_demo"], false], 0.55, 0.95],
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
      "text-halo-color": isDark() ? "#0b1112" : "#ffffff",
      "text-halo-width": 1.2,
    },
  });

  map.addLayer({
    id: "clusters",
    type: "circle",
    source: "properties",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": `rgb(${accent[0]} ${accent[1]} ${accent[2]})`,
      "circle-opacity": 0.92,
      "circle-stroke-color": "rgba(255,255,255,0.9)",
      "circle-stroke-width": 2,
      "circle-radius": [
        "step",
        ["coalesce", ["get", "total"], ["get", "point_count"]],
        17,
        10,
        21,
        50,
        27,
        200,
        33,
      ],
    },
  });
  map.addLayer({
    id: "cluster-count",
    type: "symbol",
    source: "properties",
    filter: ["has", "point_count"],
    layout: {
      "text-field": ["to-string", ["coalesce", ["get", "total"], ["get", "point_count"]]],
      "text-size": 13,
      "text-font": ["Noto Sans Bold"],
      "text-allow-overlap": true,
    },
    paint: { "text-color": "#ffffff" },
  });
  // Price bubbles: every listing shows its asking price on the map.
  const bubble = (id: string, image: string, color: string, filter: unknown) =>
    map.addLayer({
      id,
      type: "symbol",
      source: "properties",
      filter: filter as never,
      layout: {
        "text-field": ["get", "price_label"],
        "text-size": 12.5,
        "text-font": ["Noto Sans Bold"],
        "icon-image": image,
        "icon-text-fit": "both",
        "icon-text-fit-padding": [3, 9, 3, 9],
        "icon-allow-overlap": true,
        "text-allow-overlap": true,
        "symbol-sort-key": ["case", ["boolean", ["get", "is_demo"], false], 1, 0],
      },
      paint: {
        "text-color": color,
        "icon-opacity": ["case", ["boolean", ["get", "approximate"], false], 0.85, 1],
      },
    });
  bubble("price-bubbles", "bubble", ink, ["!", ["has", "point_count"]]);
  bubble("price-bubbles-active", "bubble-active", "#ffffff", ["==", ["get", "id"], ""]);
}

export function PropertyMap(props: PropertyMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const [ready, setReady] = useState(false);
  const [styleVersion, setStyleVersion] = useState(0);
  const [failed, setFailed] = useState(false);

  // Create the map once; overlays are (re)installed on every style load.
  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    let dark = false;
    const cleanups: (() => void)[] = [];
    (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (cancelled || !container.current) return;
        const { config } = latest.current;
        if (config.rtlPluginUrl && !rtlPluginRequested) {
          rtlPluginRequested = true;
          maplibre.setRTLTextPlugin(config.rtlPluginUrl, true).catch(() => undefined);
        }
        dark = isDark();
        map = new maplibre.Map({
          container: container.current,
          style: styleFor(config, dark),
          bounds: latest.current.initialBbox as LngLatBoundsLike,
          fitBoundsOptions: { padding: 24 },
          attributionControl: { compact: true, customAttribution: config.attribution },
          maxZoom: 19,
        });
        mapRef.current = map;
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-left");
        map.on("error", () => undefined); // tile errors must not crash the page

        map.on("style.load", () => {
          if (!map) return;
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

        map.on(
          "click",
          "clusters",
          async (event: MapMouseEvent & { features?: MapGeoJSONFeature[] }) => {
            const feature = event.features?.[0];
            if (!feature || !map) return;
            const serverBbox = readBboxProperty(feature.properties?.bbox);
            if (serverBbox) {
              map.fitBounds(serverBbox as LngLatBoundsLike, { padding: 40, maxZoom: 17 });
              return;
            }
            const source = map.getSource("properties") as GeoJSONSource;
            const zoom = await source.getClusterExpansionZoom(
              Number(feature.properties?.cluster_id),
            );
            const geometry = feature.geometry as Point;
            map.easeTo({ center: geometry.coordinates as [number, number], zoom, duration: 600 });
          },
        );
        map.on(
          "click",
          "price-bubbles",
          (event: MapMouseEvent & { features?: MapGeoJSONFeature[] }) => {
            const feature = event.features?.[0];
            if (!feature || !map || latest.current.drawing !== null) return;
            const p = (feature.properties ?? {}) as Record<string, unknown>;
            latest.current.onSelect(String(p.id), p);
          },
        );
        map.on("click", (event: MapMouseEvent) => {
          if (latest.current.drawing !== null) {
            latest.current.onDrawPoint([event.lngLat.lng, event.lngLat.lat]);
            return;
          }
          const hit = map?.queryRenderedFeatures(event.point, {
            layers: ["price-bubbles", "clusters"],
          });
          if (!hit?.length) latest.current.onSelect(null);
        });
        for (const layer of ["clusters", "price-bubbles"]) {
          map.on("mouseenter", layer, () => map && (map.getCanvas().style.cursor = "pointer"));
          map.on("mouseleave", layer, () => map && (map.getCanvas().style.cursor = ""));
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
        // Rendered counts for automated checks (and nothing else).
        map.on("idle", () => {
          if (!map || !container.current || !map.getLayer("price-bubbles")) return;
          const count = (layers: string[]) => map!.queryRenderedFeatures({ layers }).length;
          container.current.dataset.bubbles = String(count(["price-bubbles"]));
          container.current.dataset.clusters = String(count(["clusters"]));
          container.current.dataset.pois = String(count(["poi-dots"]));
        });
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      cleanups.forEach((fn) => fn());
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  // Data updates (re-applied after every style load).
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const labelled = props.data ? withPriceLabels(props.data as FeatureCollection) : EMPTY;
    (map.getSource("properties") as GeoJSONSource | undefined)?.setData(labelled);
  }, [ready, styleVersion, props.data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const visible = props.showBoundaries ?? true;
    (map.getSource("boundaries") as GeoJSONSource | undefined)?.setData(
      visible ? (props.boundaries ?? EMPTY) : EMPTY,
    );
  }, [ready, styleVersion, props.boundaries, props.showBoundaries]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource("pois") as GeoJSONSource | undefined)?.setData(props.pois ?? EMPTY);
  }, [ready, styleVersion, props.pois]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !map.getLayer("satellite")) return;
    map.setLayoutProperty("satellite", "visibility", props.satellite ? "visible" : "none");
  }, [ready, styleVersion, props.satellite]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const points = props.drawing ?? props.polygon ?? [];
    const features: Feature[] = points.map((coordinates) => ({
      type: "Feature",
      properties: {},
      geometry: { type: "Point", coordinates },
    }));
    if (points.length >= 3) {
      features.push({
        type: "Feature",
        properties: {},
        geometry: { type: "Polygon", coordinates: [closedRing(points)] },
      });
    } else if (points.length === 2) {
      features.push({
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: points },
      });
    }
    (map.getSource("area") as GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features,
    });
    map.getCanvas().style.cursor = props.drawing ? "crosshair" : "";
  }, [ready, styleVersion, props.drawing, props.polygon]);

  // List ↔ map: the selected/hovered listing's bubble turns accent and rises.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !map.getLayer("price-bubbles-active")) return;
    map.setFilter("price-bubbles-active", [
      "all",
      ["!", ["has", "point_count"]],
      ["==", ["get", "id"], props.highlightId ?? ""],
    ]);
  }, [ready, styleVersion, props.highlightId]);

  // Smooth camera to a requested area.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !props.focusBbox) return;
    map.fitBounds(props.focusBbox as LngLatBoundsLike, { padding: 48, duration: 900 });
  }, [ready, props.focusBbox]);

  return (
    <div className="relative h-full min-h-[420px] w-full overflow-hidden rounded-[var(--radius-media)] bg-fill">
      {/* Inline position: MapLibre adds .maplibregl-map { position: relative }, which
          overrides an `absolute` class and collapsed the map to 0px height. */}
      <div ref={container} style={{ position: "absolute", inset: 0 }} data-testid="map-canvas" />
      {!ready && !failed && (
        <p className="absolute inset-0 grid place-items-center text-sm text-ink-3">
          {props.dict.map.loading}
        </p>
      )}
      {failed && (
        <p role="alert" className="absolute inset-0 grid place-items-center text-sm text-danger">
          {props.dict.map.error}
        </p>
      )}
    </div>
  );
}
