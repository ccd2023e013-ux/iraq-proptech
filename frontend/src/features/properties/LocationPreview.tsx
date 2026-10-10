"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef, useState } from "react";

import type { MapConfig } from "@/lib/map/provider";
import { type LayerInfo, applyBasemapTone } from "@/lib/map/basemap";
import { maplibreWorkerUrl } from "@/lib/map/worker";

function isDark(): boolean {
  const forced = document.documentElement.dataset.theme;
  if (forced) return forced === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * A quiet, non-interactive map of where the listing is, using the position the
 * listing is allowed to show (`display_location`). An exact position gets a
 * pin-head dot; an approximate one is drawn as a soft area, never a point, so
 * the preview never claims more precision than the owner shared.
 */
export function LocationPreview({
  config,
  lat,
  lon,
  approximate,
  label,
}: {
  config: MapConfig;
  lat: number;
  lon: number;
  approximate: boolean;
  label: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let map: import("maplibre-gl").Map | null = null;
    (async () => {
      const maplibre = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      maplibre.setWorkerUrl(maplibreWorkerUrl(maplibre.getVersion()));
      const dark = isDark();
      map = new maplibre.Map({
        container: container.current,
        style: ((dark && config.darkStyle) || config.style) as never,
        center: [lon, lat],
        zoom: approximate ? 13.2 : 15,
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
        m.addSource("listing", {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: { type: "Point", coordinates: [lon, lat] },
            properties: {},
          },
        });
        if (approximate) {
          m.addLayer({
            id: "listing-area",
            type: "circle",
            source: "listing",
            paint: {
              "circle-radius": 46,
              "circle-color": "#06b6d4",
              "circle-opacity": 0.16,
              "circle-stroke-color": "#06b6d4",
              "circle-stroke-opacity": 0.55,
              "circle-stroke-width": 1.5,
            },
          });
        } else {
          m.addLayer({
            id: "listing-halo",
            type: "circle",
            source: "listing",
            paint: { "circle-radius": 16, "circle-color": "#10b981", "circle-opacity": 0.18 },
          });
          m.addLayer({
            id: "listing-dot",
            type: "circle",
            source: "listing",
            paint: {
              "circle-radius": 7,
              "circle-color": "#10b981",
              "circle-stroke-color": dark ? "#0b0f17" : "#ffffff",
              "circle-stroke-width": 2.5,
            },
          });
        }
        setReady(true);
      });
    })().catch(() => undefined);
    return () => {
      cancelled = true;
      map?.remove();
    };
  }, [config, lat, lon, approximate]);

  return (
    <div
      ref={container}
      role="img"
      aria-label={label}
      data-testid="location-preview"
      className={`h-56 w-full overflow-hidden rounded-[var(--radius-card)] bg-fill shadow-[inset_0_0_0_1px_var(--hairline)] transition-opacity duration-[var(--duration-slow)] ease-[var(--ease-out-soft)] sm:h-64 ${ready ? "opacity-100" : "opacity-60"}`}
    />
  );
}
