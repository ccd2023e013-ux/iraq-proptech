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
import { formatCompactPrice } from "@/lib/format";
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
  polygon: LonLat[] | null;
  drawing: LonLat[] | null;
  highlightId: string | null;
  onViewportChange: (bbox: Bbox, zoom: number) => void;
  onSelect: (id: string) => void;
  onDrawPoint: (point: LonLat) => void;
}

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
let rtlPluginRequested = false;

/** Text-only popup content (never innerHTML with listing data). */
function popupNode(props: Record<string, unknown>, dict: Dictionary, locale: Locale): HTMLElement {
  const root = document.createElement("div");
  root.className = "flex w-56 flex-col gap-1 text-sm";
  root.dir = locale === "ar" ? "rtl" : "ltr";
  if (typeof props.cover_url === "string") {
    const img = document.createElement("img");
    img.src = props.cover_url;
    img.alt = "";
    img.className = "mb-1 h-28 w-full rounded object-cover";
    root.append(img);
  }
  const title = document.createElement("strong");
  title.textContent = String((locale === "en" && props.title_en) || props.title_ar || "");
  root.append(title);
  const price = document.createElement("span");
  price.className = "font-semibold text-brand-800";
  price.textContent =
    props.price_on_request === true || props.price_amount == null
      ? dict.listing.priceOnRequest
      : (formatCompactPrice(
          String(props.price_amount),
          props.currency === "USD" ? "USD" : "IQD",
          locale,
        ) ?? "");
  root.append(price);
  if (props.approximate === true) {
    const note = document.createElement("span");
    note.className = "text-xs text-sand-500";
    note.textContent = dict.map.approximate;
    root.append(note);
  }
  if (props.is_demo === true) {
    const demo = document.createElement("span");
    demo.className = "text-xs font-semibold text-warning";
    demo.textContent = "DEMO";
    root.append(demo);
  }
  const link = document.createElement("a");
  link.href = `/properties/${encodeURIComponent(String(props.id))}`;
  link.className = "mt-1 font-medium text-brand-700 underline";
  link.textContent = dict.map.openListing;
  root.append(link);
  return root;
}

export function PropertyMap(props: PropertyMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (cancelled || !container.current) return;
        const { config } = latest.current;
        if (config.rtlPluginUrl && !rtlPluginRequested) {
          rtlPluginRequested = true;
          maplibre.setRTLTextPlugin(config.rtlPluginUrl, true).catch(() => undefined);
        }
        map = new maplibre.Map({
          container: container.current,
          style: config.style as string | StyleSpecification,
          bounds: latest.current.initialBbox as LngLatBoundsLike,
          fitBoundsOptions: { padding: 24 },
          attributionControl: { compact: true, customAttribution: config.attribution },
          maxZoom: 19,
        });
        mapRef.current = map;
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-left");
        map.on("error", () => undefined); // tile errors must not crash the page

        map.on("load", () => {
          if (!map) return;
          map.addSource("properties", {
            type: "geojson",
            data: EMPTY,
            cluster: true,
            clusterRadius: 50,
            clusterMaxZoom: 15,
            promoteId: "id",
            clusterProperties: {
              total: ["+", ["coalesce", ["get", "point_count"], 1]],
            },
          });
          map.addSource("boundaries", { type: "geojson", data: EMPTY });
          map.addSource("area", { type: "geojson", data: EMPTY });

          map.addLayer({
            id: "boundary-fill",
            type: "fill",
            source: "boundaries",
            filter: ["==", ["geometry-type"], "Polygon"],
            paint: { "fill-color": "#2f7e78", "fill-opacity": 0.05 },
          });
          map.addLayer({
            id: "boundary-line",
            type: "line",
            source: "boundaries",
            paint: { "line-color": "#22645f", "line-width": 1.5, "line-dasharray": [2, 1] },
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
            paint: { "line-color": "#8f6a22", "line-width": 2 },
          });
          map.addLayer({
            id: "area-vertices",
            type: "circle",
            source: "area",
            filter: ["==", ["geometry-type"], "Point"],
            paint: { "circle-radius": 4, "circle-color": "#8f6a22" },
          });
          map.addLayer({
            id: "clusters",
            type: "circle",
            source: "properties",
            filter: ["has", "point_count"],
            paint: {
              "circle-color": "#1d504d",
              "circle-opacity": 0.85,
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 2,
              "circle-radius": [
                "step",
                ["coalesce", ["get", "total"], ["get", "point_count"]],
                16,
                10,
                20,
                50,
                26,
                200,
                32,
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
              "text-allow-overlap": true,
            },
            paint: { "text-color": "#ffffff" },
          });
          map.addLayer({
            id: "points",
            type: "circle",
            source: "properties",
            filter: ["!", ["has", "point_count"]],
            paint: {
              "circle-color": [
                "case",
                ["boolean", ["feature-state", "highlight"], false],
                "#c99a3a",
                ["boolean", ["get", "is_demo"], false],
                "#8a8173",
                "#22645f",
              ],
              "circle-radius": ["case", ["boolean", ["feature-state", "highlight"], false], 10, 7],
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 2,
              // Approximate locations are drawn as softer markers.
              "circle-opacity": ["case", ["boolean", ["get", "approximate"], false], 0.7, 1],
            },
          });

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
              map.easeTo({ center: geometry.coordinates as [number, number], zoom });
            },
          );
          map.on("click", "points", (event: MapMouseEvent & { features?: MapGeoJSONFeature[] }) => {
            const feature = event.features?.[0];
            if (!feature || !map) return;
            const p = (feature.properties ?? {}) as Record<string, unknown>;
            const geometry = feature.geometry as Point;
            new maplibre.Popup({ closeButton: true, maxWidth: "260px" })
              .setLngLat(geometry.coordinates as [number, number])
              .setDOMContent(popupNode(p, latest.current.dict, latest.current.locale))
              .addTo(map);
            latest.current.onSelect(String(p.id));
          });
          map.on("click", (event: MapMouseEvent) => {
            if (latest.current.drawing === null) return;
            latest.current.onDrawPoint([event.lngLat.lng, event.lngLat.lat]);
          });
          for (const layer of ["clusters", "points"]) {
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
          setReady(true);
          report();
        });
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  // Data updates.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource("properties") as GeoJSONSource | undefined)?.setData(
      (props.data as FeatureCollection | null) ?? EMPTY,
    );
  }, [ready, props.data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource("boundaries") as GeoJSONSource | undefined)?.setData(props.boundaries ?? EMPTY);
  }, [ready, props.boundaries]);

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
  }, [ready, props.drawing, props.polygon]);

  // List → map highlight.
  const previous = useRef<string | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (previous.current) {
      map.setFeatureState({ source: "properties", id: previous.current }, { highlight: false });
    }
    if (props.highlightId) {
      map.setFeatureState({ source: "properties", id: props.highlightId }, { highlight: true });
    }
    previous.current = props.highlightId;
  }, [ready, props.highlightId, props.data]);

  return (
    <div className="relative h-full min-h-[420px] w-full overflow-hidden rounded-[var(--radius-card)] bg-sand-100">
      {/* Inline position: MapLibre adds .maplibregl-map { position: relative }, which
          overrides an `absolute` class and collapsed the map to 0px height. */}
      <div ref={container} style={{ position: "absolute", inset: 0 }} data-testid="map-canvas" />
      {!ready && !failed && (
        <p className="absolute inset-0 grid place-items-center text-sm text-sand-500">
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
