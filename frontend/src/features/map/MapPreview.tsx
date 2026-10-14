"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef, useState } from "react";

import { easeStandard, placeTagsBalanced } from "@/lib/map/camera";
import type { MapConfig } from "@/lib/map/provider";
import { styleFor } from "@/lib/map/style";
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

/** The home arrival: one camera move (ms). */
const INTRO_MS = 1800;

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
        style: styleFor(
          config,
          dark,
          document.documentElement.lang === "en" ? "en" : "ar",
        ) as never,
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
        // Price tags: the map page's markers, hidden until placed.
        const tagEls: {
          el: HTMLDivElement;
          tag: HTMLElement;
          badge: HTMLElement;
          p: PreviewPoint;
        }[] = [];
        const tagged = points.filter((p) => tags && p.label && p.precision === "exact");
        // Every listing's dot first, so no dot is ever drawn over a tag.
        for (const p of tagged) {
          const dot = document.createElement("div");
          dot.setAttribute("aria-hidden", "true");
          dot.style.cssText =
            "width:7px;height:7px;border-radius:999px;background:var(--spatial-fill);box-shadow:0 0 0 1.5px var(--canvas);";
          new maplibre.Marker({ element: dot }).setLngLat([p.lon, p.lat]).addTo(m);
        }
        for (const p of tagged) {
          const el = document.createElement("div");
          el.className = "map-tag-anchor";
          el.setAttribute("aria-hidden", "true");
          el.style.visibility = "hidden";
          const tag = document.createElement("span");
          tag.className = "map-tag";
          tag.style.pointerEvents = "none";
          tag.style.animation = "none"; // arrives when it is revealed (below)
          const value = document.createElement("span");
          value.textContent = p.label ?? "";
          const badge = document.createElement("span");
          badge.className = "map-tag-more";
          tag.append(value, badge);
          el.appendChild(tag);
          new maplibre.Marker({ element: el, anchor: "bottom", offset: [0, -8] })
            .setLngLat([p.lon, p.lat])
            .addTo(m);
          tagEls.push({ el, tag, badge, p });
        }
        // Other points: area discs carry only their key number; exact points
        // are dots (dense) or numbered pins.
        for (const p of points) {
          if (tags && p.label && p.precision === "exact") continue;
          const el = document.createElement("div");
          el.setAttribute("aria-hidden", "true");
          const color = TONE[p.tone ?? "accent"];
          if (p.precision === "area") {
            if (!p.label) continue;
            el.style.cssText = `color:${color};font:700 12px/1 var(--font-sans);text-shadow:0 0 3px var(--canvas);`;
          } else {
            el.style.cssText = dense
              ? `width:8px;height:8px;border-radius:999px;background:${color};box-shadow:0 0 0 2px var(--canvas);`
              : `display:grid;place-items:center;min-width:${p.label ? 22 : 14}px;height:${p.label ? 22 : 14}px;padding:0 5px;border-radius:999px;background:${color};color:#04130d;font:600 11px/1 var(--font-sans);border:2px solid var(--canvas);box-shadow:0 0 0 6px ${color}2e;`;
          }
          if (p.label) el.textContent = p.label;
          new maplibre.Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(m);
        }
        // Placement is computed for the camera's final position, so it is
        // right whether or not the arrival move runs (and never waits for it).
        const place = () => {
          const boxes = tagEls.map(({ tag, p }, i) => {
            const at = m.project([p.lon, p.lat]);
            const width = tag.offsetWidth || 80;
            return { id: String(i), x: at.x - width / 2, y: at.y - 36, width, height: 28 };
          });
          // Only tags fully inside the open part of the frame (not under the
          // text column on wide screens, not cut by an edge).
          const w = el.clientWidth;
          const h = el.clientHeight;
          const wide = window.matchMedia("(min-width: 768px)").matches;
          const inset = startInset && wide ? w * startInset : 0;
          const rtl = document.documentElement.dir === "rtl";
          const visibleBoxes = boxes.filter(
            (b) =>
              b.x > (rtl ? 8 : inset + 8) &&
              b.x + b.width < (rtl ? w - inset - 8 : w - 8) &&
              b.y > 8 &&
              b.y + b.height < h - 48,
          );
          const placed = placeTagsBalanced(visibleBoxes, 18, { gap: 8, cell: 120, absorb: 56 });
          el.dataset.tagsTotal = String(boxes.length);
          el.dataset.tagsShown = String(placed.shown.size);
          return placed;
        };
        const reveal = ({ shown, more }: ReturnType<typeof place>, stagger: number) => {
          let order = 0;
          tagEls.forEach(({ el: anchor, tag, badge }, i) => {
            const on = shown.has(String(i));
            anchor.style.visibility = on ? "visible" : "hidden";
            const extra = more.get(String(i)) ?? 0;
            badge.textContent = extra > 0 ? `+${extra}` : "";
            if (on) {
              tag.style.animation = "";
              tag.style.animationDelay = `${order * stagger}ms`;
              order += 1;
            }
          });
        };
        // Fade in once the tiles are drawn, not while the basemap is half-loaded.
        m.once("idle", () => {
          setReady(true);
          const placed = place();
          const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          if (intro && !reduce) {
            // One arrival: the camera settles in from slightly wider, and the
            // prices rise in order as it lands (most of the move is early).
            el.dataset.phase = "intro";
            const target = { zoom: m.getZoom(), center: m.getCenter() };
            m.jumpTo({ zoom: target.zoom - 0.8 });
            m.easeTo({ ...target, duration: INTRO_MS, easing: easeStandard });
            window.setTimeout(() => reveal(placed, 60), INTRO_MS * 0.35);
            m.once("moveend", () => {
              el.dataset.phase = "settled";
            });
          } else {
            reveal(placed, 0);
            el.dataset.phase = "settled";
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
