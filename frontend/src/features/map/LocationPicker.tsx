"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { LngLatBoundsLike, Map as MapLibreMap, Marker, StyleSpecification } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import type { MapConfig } from "@/lib/map/provider";

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
  onPickRef.current = onPick;
  const [resolved, setResolved] = useState<Resolved | null>(null);
  const [outside, setOutside] = useState(false);
  const f = dict.listingForm;

  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    (async () => {
      const maplibre = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      const start = lat !== null && lon !== null;
      map = new maplibre.Map({
        container: container.current,
        style: config.style as string | StyleSpecification,
        ...(start
          ? { center: [lon as number, lat as number] as [number, number], zoom: 15 }
          : { bounds: config.defaultBbox as LngLatBoundsLike }),
        attributionControl: { compact: true, customAttribution: config.attribution },
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-left");
      const marker = new maplibre.Marker({ draggable: true, color: "#1d504d" });
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
    if (lat === null || lon === null || !Number.isFinite(lat) || !Number.isFinite(lon)) {
      setResolved(null);
      return;
    }
    const map = mapRef.current;
    if (map && markerRef.current) markerRef.current.setLngLat([lon, lat]).addTo(map);
    let cancelled = false;
    const timer = setTimeout(() => {
      apiFetch<Resolved>(`/api/v1/locations/resolve?lat=${lat}&lon=${lon}`)
        .then((r) => {
          if (cancelled) return;
          setResolved(r);
          setOutside(false);
        })
        .catch(() => {
          if (cancelled) return;
          setResolved(null);
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
