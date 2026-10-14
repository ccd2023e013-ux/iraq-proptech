"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef, useState } from "react";

import { type LayerInfo, applyBasemapTone } from "@/lib/map/basemap";
import { easeStandard, placeTags } from "@/lib/map/camera";
import type { MapConfig } from "@/lib/map/provider";
import { maplibreWorkerUrl } from "@/lib/map/worker";

export type PreviewTone = "accent" | "gold" | "muted";

export interface PreviewPoint {
  lon: number;
  lat: number;
  /** "exact" draws a pin-head dot; "area" a soft disc that never reads as a site. */
  precision: "exact" | "area";
  tone?: PreviewTone;
  /** Short visible label (e.g. a number keyed to a list, or a price tag). */
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
  dense = false,
  tags = false,
  intro = false,
  startInset = 0,
}: {
  config: MapConfig;
  points: PreviewPoint[];
  label: string;
  className?: string;
  /** Many points (e.g. a city's listings): small dots without halos. */
  dense?: boolean;
  /** Labelled points are drawn as price tags (the map page's tags), placed
   * without overlap once the camera settles. */
  tags?: boolean;
  /** One orchestrated arrival: the camera settles in from slightly wider
   * (instant under reduced motion). Used once, on the home page. */
  intro?: boolean;
  /** On wide screens, keep this share of the width (at the reading start)
   * clear of points: the map composes itself beside the text. */
  startInset?: number;
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
      const el = container.current;
      const framePadding = () => {
        const wide = window.matchMedia("(min-width: 768px)").matches;
        if (!startInset || !wide) return 56;
        const start = Math.round(el.clientWidth * startInset);
        const rtl = document.documentElement.dir === "rtl";
        return { top: 96, bottom: 96, left: rtl ? 72 : start, right: rtl ? start : 72 };
      };
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
              fitBoundsOptions: { padding: framePadding(), maxZoom: 13 },
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
        // Price tags: positioned as markers, shown only where they fit.
        const tagEls: { el: HTMLDivElement; p: PreviewPoint; width: number }[] = [];
        for (const p of points) {
          if (!(tags && p.label && p.precision === "exact")) continue;
          const el = document.createElement("div");
          el.className = "map-tag-anchor";
          el.setAttribute("aria-hidden", "true");
          el.style.visibility = "hidden";
          const tag = document.createElement("span");
          tag.className = "map-tag";
          tag.style.pointerEvents = "none";
          tag.style.animation = "none"; // arrives when it is placed (below)
          tag.textContent = p.label;
          el.appendChild(tag);
          new maplibre.Marker({ element: el, anchor: "bottom", offset: [0, -7] })
            .setLngLat([p.lon, p.lat])
            .addTo(m);
          tagEls.push({ el, p, width: 0 });
        }
        const placeAll = () => {
          if (!tagEls.length) return;
          const boxes = tagEls.map(({ el, p }, i) => {
            const at = m.project([p.lon, p.lat]);
            const width = (el.firstElementChild as HTMLElement).offsetWidth || 80;
            return { id: String(i), x: at.x - width / 2, y: at.y - 34, width, height: 26 };
          });
          const shown = placeTags(boxes, 24, 8);
          let order = 0;
          tagEls.forEach(({ el }, i) => {
            const on = shown.has(String(i));
            el.style.visibility = on ? "visible" : "hidden";
            if (on) {
              // A short, ordered arrival — the one staged moment on the page.
              const tag = el.firstElementChild as HTMLElement;
              tag.style.animation = "";
              tag.style.animationDelay = `${order * 70}ms`;
              order += 1;
            }
          });
        };
        for (const p of points) {
          if (tags && p.label && p.precision === "exact") {
            // The dot under each tag marks the exact spot.
            const dot = document.createElement("div");
            dot.setAttribute("aria-hidden", "true");
            dot.style.cssText = `width:7px;height:7px;border-radius:999px;background:var(--spatial-fill);box-shadow:0 0 0 2px var(--canvas);`;
            new maplibre.Marker({ element: dot }).setLngLat([p.lon, p.lat]).addTo(m);
            continue;
          }
          const el = document.createElement("div");
          el.setAttribute("aria-hidden", "true");
          const color = TONE[p.tone ?? "accent"];
          if (p.precision === "area") {
            // Only the key number, never a dot: the disc already says "around here".
            if (!p.label) continue;
            el.style.cssText = `color:${color};font:700 12px/1 var(--font-sans);text-shadow:0 0 3px ${dark ? "#0b0f17" : "#ffffff"};`;
          } else {
            el.style.cssText = dense
              ? `width:8px;height:8px;border-radius:999px;background:${color};box-shadow:0 0 0 2px ${dark ? "#0a0c0f" : "#ffffff"};`
              : `display:grid;place-items:center;min-width:${p.label ? 22 : 14}px;height:${p.label ? 22 : 14}px;padding:0 5px;border-radius:999px;background:${color};color:#04130d;font:600 11px/1 var(--font-sans);border:2px solid ${dark ? "#0a0c0f" : "#ffffff"};box-shadow:0 0 0 6px ${color}2e;`;
          }
          if (p.label) el.textContent = p.label;
          new maplibre.Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(m);
        }
        // Fade in once the tiles are drawn, not while the basemap is half-loaded.
        m.once("idle", () => {
          setReady(true);
          const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          if (intro && !reduce) {
            const target = { zoom: m.getZoom(), center: m.getCenter() };
            m.jumpTo({ zoom: target.zoom - 0.9 });
            m.once("moveend", placeAll);
            m.easeTo({ ...target, duration: 2400, easing: easeStandard });
          } else {
            placeAll();
          }
        });
      });
    })().catch(() => undefined);
    return () => {
      cancelled = true;
      map?.remove();
    };
    // `key` captures the points; config is static per page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, config, dense, tags, intro, startInset]);

  return (
    <div
      ref={container}
      role="img"
      aria-label={label}
      data-testid="map-preview"
      data-ready={ready ? "1" : "0"}
      className={`relative isolate w-full overflow-hidden rounded-[var(--radius-card)] bg-fill shadow-[inset_0_0_0_1px_var(--hairline)] transition-opacity duration-[var(--duration-slow)] ease-[var(--ease-out-soft)] ${ready ? "opacity-100" : "opacity-50"} ${className}`}
    />
  );
}
