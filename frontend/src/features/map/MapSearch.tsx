"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { priceLabel } from "@/features/properties/PropertyCard";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { formatArea, placeName } from "@/lib/format";
import {
  type Bbox,
  formatBbox,
  formatPolygon,
  type LonLat,
  parsePolygon,
  polygonBbox,
} from "@/lib/map/geo";
import { type MapConfig, parseBbox } from "@/lib/map/provider";
import { type RawParams, first, toApiQuery, withParam } from "@/lib/search";
import type { PropertyCard } from "@/types/property";

import { type MapFeatureCollection, PropertyMap } from "./PropertyMap";
import type { FeatureCollection } from "geojson";

export interface MapSearchProps {
  config: MapConfig;
  dict: Dictionary;
  locale: Locale;
  params: RawParams;
  items: PropertyCard[];
  total: number;
  boundaries: FeatureCollection | null;
  initialBbox: Bbox;
}

/**
 * Map + list kept in sync through the URL: moving the map writes `bbox` to
 * the query string, the server re-renders the list for that viewport, and the
 * map loads GeoJSON for the same filters. Drawing an area replaces the
 * viewport filter with a polygon.
 */
export function MapSearch({
  config,
  dict,
  locale,
  params,
  items,
  total,
  boundaries,
  initialBbox,
}: MapSearchProps) {
  const router = useRouter();
  const pathname = usePathname();
  const m = dict.map;
  const polygon = useMemo(() => parsePolygon(first(params.polygon)), [params.polygon]);
  const [followMap, setFollowMap] = useState(!polygon);
  const [drawing, setDrawing] = useState<LonLat[] | null>(null);
  const [data, setData] = useState<MapFeatureCollection | null>(null);
  const [error, setError] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [view, setView] = useState<"map" | "list">("map");
  const zoomRef = useRef(12);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const paramsRef = useRef(params);
  paramsRef.current = params;

  // Map data for the current filters (the query string minus pagination/sort).
  const dataQuery = useMemo(() => {
    const { page: _page, sort: _sort, ...filters } = params;
    void _page;
    void _sort;
    return toApiQuery(filters);
  }, [params]);

  const load = useCallback(async (query: string, zoom: number) => {
    try {
      const sep = query ? "&" : "";
      setData(
        await apiFetch<MapFeatureCollection>(`/api/v1/map/properties?${query}${sep}zoom=${zoom}`),
      );
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    void load(dataQuery, zoomRef.current);
  }, [dataQuery, load]);

  const navigate = useCallback(
    (query: string) => router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false }),
    [router, pathname],
  );

  const onViewportChange = useCallback(
    (bbox: Bbox, zoom: number) => {
      const zoomChanged = zoom !== zoomRef.current;
      zoomRef.current = zoom;
      if (!followMap || drawing) {
        if (zoomChanged) void load(dataQuery, zoom);
        return;
      }
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        const next = withParam(paramsRef.current, "bbox", formatBbox(bbox));
        if (next === toApiQuery(paramsRef.current)) {
          if (zoomChanged) void load(dataQuery, zoom);
          return;
        }
        navigate(next);
      }, 450);
    },
    [followMap, drawing, navigate, load, dataQuery],
  );

  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  function finishDrawing() {
    if (!drawing || drawing.length < 3) return;
    const next: RawParams = { ...paramsRef.current, polygon: formatPolygon(drawing) };
    delete next.bbox;
    delete next.page;
    setDrawing(null);
    setFollowMap(false);
    navigate(toApiQuery(next));
  }

  function clearArea() {
    setFollowMap(true);
    navigate(withParam(paramsRef.current, "polygon", null));
  }

  const clustered = data?.meta?.mode === "clusters";
  const demoBoundary = boundaries?.features.some((f) =>
    String(f.properties?.geometry_source ?? "").startsWith("DEMO"),
  );
  const sources = Array.from(
    new Set(
      (boundaries?.features ?? [])
        .map((f) => f.properties?.geometry_source as string | undefined)
        .filter((s): s is string => !!s),
    ),
  );
  const startBbox = polygon ? polygonBbox(polygon) : (parseBbox(first(params.bbox)) ?? initialBbox);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-sand-700">
          <input
            type="checkbox"
            checked={followMap}
            disabled={!!polygon || !!drawing}
            onChange={(e) => setFollowMap(e.target.checked)}
          />
          {m.searchAsMove}
        </label>
        <div className="ms-auto flex flex-wrap gap-2">
          {drawing ? (
            <>
              <Button onClick={finishDrawing} disabled={drawing.length < 3}>
                {m.finishDrawing}
              </Button>
              <Button variant="ghost" onClick={() => setDrawing(null)}>
                {m.cancelDrawing}
              </Button>
            </>
          ) : (
            <Button variant="secondary" onClick={() => setDrawing([])}>
              {m.drawArea}
            </Button>
          )}
          {polygon && !drawing && (
            <Button variant="ghost" onClick={clearArea}>
              {m.clearArea}
            </Button>
          )}
          <div className="flex rounded-lg border border-sand-200 lg:hidden" role="group">
            {(["map", "list"] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`px-3 py-1.5 text-sm ${view === v ? "bg-brand-700 text-white" : ""}`}
              >
                {v === "map" ? m.showMap : m.showList}
              </button>
            ))}
          </div>
        </div>
      </div>
      {drawing && <p className="text-sm text-gold-700">{m.drawHint}</p>}

      <div className="grid gap-4 lg:grid-cols-[minmax(320px,420px)_1fr]">
        <section
          aria-label={m.showList}
          className={`flex max-h-[70vh] flex-col gap-3 overflow-y-auto ${view === "map" ? "hidden lg:flex" : ""}`}
        >
          <p className="text-sm text-sand-700 tabular">
            {total} {m.inView}
          </p>
          {items.length === 0 && (
            <p className="rounded-[var(--radius-card)] border border-dashed border-sand-200 py-10 text-center text-sm text-sand-500">
              {dict.search.noResults}
            </p>
          )}
          <ul className="flex flex-col gap-2">
            {items.map((card) => {
              const title = locale === "en" && card.title_en ? card.title_en : card.title_ar;
              return (
                <li key={card.id}>
                  <a
                    href={`/properties/${card.id}`}
                    onMouseEnter={() => setHighlightId(card.id)}
                    onMouseLeave={() => setHighlightId(null)}
                    onFocus={() => setHighlightId(card.id)}
                    className={`flex gap-3 rounded-[var(--radius-card)] border bg-white p-2 transition ${highlightId === card.id ? "border-gold-500" : "border-sand-200"}`}
                  >
                    {card.cover_url ? (
                      // eslint-disable-next-line @next/next/no-img-element -- served by our API
                      <img
                        src={card.cover_url}
                        alt=""
                        className="h-20 w-24 shrink-0 rounded object-cover"
                      />
                    ) : (
                      <div className="h-20 w-24 shrink-0 rounded bg-sand-100" />
                    )}
                    <div className="flex min-w-0 flex-col gap-0.5 text-sm">
                      <span className="truncate font-semibold text-sand-900">{title}</span>
                      <span className="font-bold text-brand-800 tabular">
                        {priceLabel(card, dict, locale)}
                      </span>
                      <span className="truncate text-xs text-sand-500">
                        {[placeName(card.district ?? null, locale), placeName(card.city, locale)]
                          .filter(Boolean)
                          .join("، ")}
                        {card.area_m2 ? ` · ${formatArea(card.area_m2, locale)}` : ""}
                      </span>
                      {card.is_demo && (
                        <span className="text-xs font-semibold text-warning">DEMO</span>
                      )}
                    </div>
                  </a>
                </li>
              );
            })}
          </ul>
          {total > items.length && (
            <a
              href={`/properties?${toApiQuery(params)}`}
              className="text-center text-sm font-medium text-brand-700"
            >
              {dict.landing.viewAll}
            </a>
          )}
        </section>

        <section className={`flex flex-col gap-2 ${view === "list" ? "hidden lg:flex" : ""}`}>
          <div className="h-[70vh]">
            <PropertyMap
              config={config}
              dict={dict}
              locale={locale}
              initialBbox={startBbox}
              data={data}
              boundaries={boundaries}
              polygon={polygon}
              drawing={drawing}
              highlightId={highlightId}
              onViewportChange={onViewportChange}
              onSelect={setHighlightId}
              onDrawPoint={(p) => setDrawing((d) => (d ? [...d, p] : d))}
            />
          </div>
          <div className="flex flex-col gap-1 text-xs text-sand-500">
            {error && <p className="text-danger">{m.error}</p>}
            {clustered && <p>{m.clustered}</p>}
            <p>{m.hiddenNotOnMap}</p>
            {sources.length > 0 && (
              <p>
                {m.boundarySource}: {sources.join(" · ")}
                {demoBoundary && <strong className="ms-1 text-warning">({m.demoBoundary})</strong>}
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
