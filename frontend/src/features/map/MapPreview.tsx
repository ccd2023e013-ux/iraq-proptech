"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef, useState } from "react";

import { type LayerInfo, applyBasemapTone } from "@/lib/map/basemap";
import type { MapConfig } from "@/lib/map/provider";
import { maplibreWorkerUrl } from "@/lib/map/worker";

export type PreviewTone = "accent" | "gold" | "muted";

export interface PreviewPoint {
  lon: number;
  lat: number;
  /** "exact" draws a pin-head dot; "area" a soft disc that never reads as a site. */
  precision: "exact" | "area";
  tone?: PreviewTone;
  /** Short visible label (e.g. a number keyed to a list). */
  label?: string;
}

const TONE: Record<PreviewTone, string> = {
  accent: "#10b981",
  gold: "#c99a3c",
  muted: "#7c879c",
};

function isDark(): boolean {
  const forced = document.documentElement.dataset.theme;
  if (forced) return forced === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * A quiet, non-interactive map: real geography under a few points, toned like
 * the main map. Used where a place matters but exploring does not (a listing's
 * location, the Future Iraq header). The basemap fades in once it is drawn.
 */
export function MapPreview({
  config,
  points,
  label,
  className = "h-56 sm:h-64",
}: {
  config: MapConfig;
  points: PreviewPoint[];
  label: string;
  className?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const key = JSON.stringify(points);

  useEffect(() => {
    if (!points.length) return;
    let cancelled = false;
    let map: import("maplibre-gl").Map | null = null;
    (async () => {
      const maplibre = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      maplibre.setWorkerUrl(maplibreWorkerUrl(maplibre.getVersion()));
      const dark = isDark();
      const single = points.length === 1 ? points[0] : null;
      const lons = points.map((p) => p.lon);
      const lats = points.map((p) => p.lat);
      map = new maplibre.Map({
        container: container.current,
        style: ((dark && config.darkStyle) || config.style) as never,
        ...(single
          ? {
              center: [single.lon, single.lat] as [number, number],
              zoom: single.precision === "area" ? 13.2 : 15,
            }
          : {
              bounds: [
                [Math.min(...lons), Math.min(...lats)],
                [Math.max(...lons), Math.max(...lats)],
              ] as [[number, number], [number, number]],
              fitBoundsOptions: { padding: 56, maxZoom: 13 },
            }),
        interactive: false,
        attributionControl: { compact: true },
      });
      const m = map;
      m.on("style.load", () => {
        if (config.provider === "openfreemap") {
          applyBasemapTone(
            { setPaintProperty: (l, p, v) => m.setPaintProperty(l, p as never, v as never) },
            m.getStyle().layers as LayerInfo[],
            dark,
          );
        }
        const areas = points.filter((p) => p.precision === "area");
        if (areas.length) {
          m.addSource("preview-areas", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: areas.map((p) => ({
                type: "Feature",
                geometry: { type: "Point", coordinates: [p.lon, p.lat] },
                properties: { color: TONE[p.tone ?? "accent"] },
              })),
            },
          });
          m.addLayer({
            id: "preview-areas",
            type: "circle",
            source: "preview-areas",
            paint: {
              "circle-radius": single ? 46 : 22,
              "circle-color": ["get", "color"] as never,
              "circle-opacity": 0.16,
              "circle-stroke-color": ["get", "color"] as never,
              "circle-stroke-opacity": 0.6,
              "circle-stroke-width": 1.5,
            },
          });
        }
        for (const p of points) {
          const el = document.createElement("div");
          el.setAttribute("aria-hidden", "true");
          const color = TONE[p.tone ?? "accent"];
          if (p.precision === "area") {
            // Only the key number, never a dot: the disc already says "around here".
            if (!p.label) continue;
            el.style.cssText = `color:${color};font:700 12px/1 var(--font-sans);text-shadow:0 0 3px ${dark ? "#0b0f17" : "#ffffff"};`;
          } else {
            el.style.cssText = `display:grid;place-items:center;min-width:${p.label ? 22 : 14}px;height:${p.label ? 22 : 14}px;padding:0 5px;border-radius:999px;background:${color};color:#04130d;font:600 11px/1 var(--font-sans);border:2px solid ${dark ? "#0b0f17" : "#ffffff"};box-shadow:0 0 0 6px ${color}2e;`;
          }
          if (p.label) el.textContent = p.label;
          new maplibre.Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(m);
        }
        setReady(true);
      });
    })().catch(() => undefined);
    return () => {
      cancelled = true;
      map?.remove();
    };
    // `key` captures the points; config is static per page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, config]);

  return (
    <div
      ref={container}
      role="img"
      aria-label={label}
      data-testid="map-preview"
      className={`w-full overflow-hidden rounded-[var(--radius-card)] bg-fill shadow-[inset_0_0_0_1px_var(--hairline)] transition-opacity duration-[var(--duration-slow)] ease-[var(--ease-out-soft)] ${ready ? "opacity-100" : "opacity-50"} ${className}`}
    />
  );
}
