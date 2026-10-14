"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { LngLatBoundsLike, Map as MapLibreMap, Marker } from "maplibre-gl";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import type { MapConfig } from "@/lib/map/provider";
import { styleFor } from "@/lib/map/style";
import { maplibreWorkerUrl } from "@/lib/map/worker";

interface PlaceSummary {
  id: string;
  name_ar: string;
  name_en: string;
}

export interface Resolved {
  governorate: PlaceSummary | null;
  city: PlaceSummary | null;
  district: PlaceSummary | null;
  neighborhood: PlaceSummary | null;
  method: "boundary" | "nearest_city_centroid" | "none";
  approximate: boolean;
}

/**
 * Click (or drag the marker) to set the listing's exact point. The containing
 * area is *suggested* from boundaries/centroids; the lister decides whether to
 * apply it — nothing is filled in silently.
 */
export function LocationPicker({
  config,
  dict,
  locale,
  lat,
  lon,
  onPick,
  onApply,
}: {
  config: MapConfig;
  dict: Dictionary;
  locale: Locale;
  lat: number | null;
  lon: number | null;
  onPick: (lat: number, lon: number) => void;
  onApply: (resolved: Resolved) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const onPickRef = useRef(onPick);
  useLayoutEffect(() => {
    onPickRef.current = onPick;
  });
  const valid = lat !== null && lon !== null && Number.isFinite(lat) && Number.isFinite(lon);
  const point = valid ? `${lat},${lon}` : null;
  // The area resolved for a point; shown only while that point is still the one typed.
  const [lookup, setLookup] = useState<{ point: string; area: Resolved | null } | null>(null);
  const resolved = point && lookup?.point === point ? lookup.area : null;
  const [outside, setOutside] = useState(false);
  const f = dict.listingForm;

  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    (async () => {
      const maplibre = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      maplibre.setWorkerUrl(maplibreWorkerUrl(maplibre.getVersion()));
      const start = lat !== null && lon !== null;
      map = new maplibre.Map({
        container: container.current,
        style: styleFor(
          config,
          document.documentElement.dataset.theme === "dark" ||
            (!document.documentElement.dataset.theme &&
              window.matchMedia("(prefers-color-scheme: dark)").matches),
          document.documentElement.lang === "en" ? "en" : "ar",
        ),
        ...(start
          ? { center: [lon as number, lat as number] as [number, number], zoom: 15 }
          : { bounds: config.defaultBbox as LngLatBoundsLike }),
        attributionControl: {
          compact: true,
          // OpenFreeMap tiles carry their own credits; avoid printing them twice.
          customAttribution: config.provider === "openfreemap" ? undefined : config.attribution,
        },
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-left");
      const marker = new maplibre.Marker({ draggable: true, color: "#10b981" });
      markerRef.current = marker;
      if (start) marker.setLngLat([lon as number, lat as number]).addTo(map);
      marker.on("dragend", () => {
        const p = marker.getLngLat();
        onPickRef.current(Number(p.lat.toFixed(6)), Number(p.lng.toFixed(6)));
      });
      map.on("click", (event) => {
        if (!map) return;
        marker.setLngLat(event.lngLat).addTo(map);
        onPickRef.current(Number(event.lngLat.lat.toFixed(6)), Number(event.lngLat.lng.toFixed(6)));
      });
    })().catch(() => undefined);
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
    // The map is created once; later prop changes move the marker below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep marker in sync with typed coordinates and resolve the area.
  useEffect(() => {
    if (lat === null || lon === null || !Number.isFinite(lat) || !Number.isFinite(lon)) return;
    const map = mapRef.current;
    if (map && markerRef.current) markerRef.current.setLngLat([lon, lat]).addTo(map);
    let cancelled = false;
    const timer = setTimeout(() => {
      apiFetch<Resolved>(`/api/v1/locations/resolve?lat=${lat}&lon=${lon}`)
        .then((r) => {
          if (cancelled) return;
          setLookup({ point: `${lat},${lon}`, area: r });
          setOutside(false);
        })
        .catch(() => {
          if (cancelled) return;
          setLookup({ point: `${lat},${lon}`, area: null });
          setOutside(true);
        });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [lat, lon]);

  const name = (p: PlaceSummary | null) => (p ? (locale === "ar" ? p.name_ar : p.name_en) : null);
  const label = resolved
    ? [resolved.neighborhood, resolved.district, resolved.city, resolved.governorate]
        .map(name)
        .filter(Boolean)
        .join("، ")
    : "";

  return (
    <div className="flex flex-col gap-2">
      <div
        ref={container}
        className="h-72 w-full overflow-hidden rounded-lg border border-sand-200"
      />
      <p className="text-xs text-sand-500">{f.mapHint}</p>
      {outside && <p className="text-sm text-danger">{f.outsideIraq}</p>}
      {resolved && resolved.method !== "none" && label && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-sand-100 px-3 py-2 text-sm">
          <span>
            {f.suggestedArea}: <strong>{label}</strong>
            {resolved.approximate && (
              <span className="ms-1 text-xs text-sand-500">({f.suggestionApproximate})</span>
            )}
          </span>
          <Button size="sm" variant="secondary" onClick={() => onApply(resolved)}>
            {f.applySuggestion}
          </Button>
        </div>
      )}
    </div>
  );
}
