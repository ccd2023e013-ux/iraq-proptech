"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  type ReactNode,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { SafeImage } from "@/components/ui/SafeImage";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { priceLabel } from "@/features/properties/PropertyCard";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { formatArea, formatCompactPrice, placeName } from "@/lib/format";
import {
  type Bbox,
  formatBbox,
  formatPolygon,
  type LonLat,
  parsePolygon,
  polygonBbox,
} from "@/lib/map/geo";
import { PLACE_GROUPS, bboxAround, placesAllowed } from "@/lib/map/places";
import { type MapConfig, parseBbox } from "@/lib/map/provider";
import { stagger } from "@/lib/motion";
import { type RawParams, first, toApiQuery, withParam } from "@/lib/search";
import type { PropertyCard } from "@/types/property";

import { type MapFeatureCollection, POI_COLORS, PropertyMap } from "./PropertyMap";
import type { Feature, FeatureCollection } from "geojson";

export interface MapSearchProps {
  config: MapConfig;
  dict: Dictionary;
  locale: Locale;
  params: RawParams;
  items: PropertyCard[];
  total: number;
  boundaries: FeatureCollection | null;
  initialBbox: Bbox;
  /** Search filters (server-rendered) shown in the results panel. */
  filters?: ReactNode;
}

interface Poi {
  id: string;
  category: string;
  name_ar: string;
  name_en: string | null;
  lat: number;
  lon: number;
  source: string;
  is_demo: boolean;
}

/**
 * Map + list kept in sync through the URL: moving the map writes `bbox` to
 * the query string, the server re-renders the list for that viewport, and the
 * map loads GeoJSON for the same filters. Drawing an area or "near me"
 * replaces the viewport filter with a polygon or a radius.
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
  filters,
}: MapSearchProps) {
  const router = useRouter();
  const pathname = usePathname();
  const m = dict.map;
  const polygon = useMemo(() => parsePolygon(first(params.polygon)), [params.polygon]);
  const nearActive = !!first(params.near_lat);
  const [followMap, setFollowMap] = useState(!polygon && !nearActive);
  const [drawing, setDrawing] = useState<LonLat[] | null>(null);
  const [data, setData] = useState<MapFeatureCollection | null>(null);
  const [error, setError] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [view, setView] = useState<"map" | "list">("map");
  const [placeGroups, setPlaceGroups] = useState<Set<string>>(new Set());
  const [showAreas, setShowAreas] = useState(true);
  const [satellite, setSatellite] = useState(false);
  const [loadedPois, setPois] = useState<FeatureCollection | null>(null);
  const [future, setFuture] = useState(first(params.layer) === "future");
  const [projects, setProjects] = useState<FeatureCollection | null>(null);
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [viewport, setViewport] = useState<Bbox | null>(null);
  const [focusBbox, setFocusBbox] = useState<Bbox | null>(null);
  const [geoError, setGeoError] = useState(false);
  const zoomRef = useRef(12);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Whether viewport moves may navigate. Kept in a ref and switched inside the
  // click handlers themselves: a map 'moveend' can arrive between a click and
  // React's commit (e.g. the end of a pan's inertia right after "Draw area"),
  // and must already see the new mode.
  const mode = useRef({ follow: followMap, drawing: false });
  useLayoutEffect(() => {
    mode.current = { follow: followMap, drawing: drawing !== null };
  }, [followMap, drawing]);
  // Committed URL params for timers and event handlers (never a render that was
  // discarded or is still pending).
  const paramsRef = useRef(params);
  useLayoutEffect(() => {
    paramsRef.current = params;
  }, [params]);

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

  // Places for the visible area and the chosen groups.
  const placesQuery = useMemo(() => {
    if (placeGroups.size === 0 || !placesAllowed(viewport) || !viewport) return null;
    const categories = PLACE_GROUPS.filter((g) => placeGroups.has(g.key)).flatMap(
      (g) => g.categories,
    );
    const q = new URLSearchParams({ bbox: viewport.map((v) => v.toFixed(4)).join(",") });
    categories.forEach((c) => q.append("category", c));
    return q.toString();
  }, [placeGroups, viewport]);

  // Kept while the area changes (no flicker on pan); hidden when places are off.
  const pois = placesQuery ? loadedPois : null;

  useEffect(() => {
    if (!placesQuery) return;
    let stale = false;
    const handle = setTimeout(() => {
      apiFetch<Poi[]>(`/api/v1/pois?${placesQuery}`)
        .then((rows) => {
          if (stale) return;
          setPois({
            type: "FeatureCollection",
            features: rows.map(
              (p): Feature => ({
                type: "Feature",
                id: p.id,
                geometry: { type: "Point", coordinates: [p.lon, p.lat] },
                properties: {
                  category: p.category,
                  is_demo: p.is_demo,
                  label: (locale === "en" && p.name_en) || p.name_ar,
                },
              }),
            ),
          });
        })
        .catch(() => !stale && setPois(null));
    }, 250);
    return () => {
      stale = true;
      clearTimeout(handle);
    };
  }, [placesQuery, locale]);

  // Future Iraq projects (few, cached by the API): loaded once when the layer is on.
  useEffect(() => {
    if (!future || projects) return;
    apiFetch<FeatureCollection>("/api/v1/development/projects")
      .then((fc) =>
        setProjects({
          ...fc,
          features: fc.features.map((f) => ({
            ...f,
            properties: {
              ...f.properties,
              label: (locale === "en" && f.properties?.name_en) || f.properties?.name_ar,
            },
          })),
        }),
      )
      .catch(() => setProjects(null));
  }, [future, projects, locale]);

  const navigate = useCallback(
    (query: string) => router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false }),
    [router, pathname],
  );

  const onViewportChange = useCallback(
    (bbox: Bbox, zoom: number) => {
      setViewport(bbox);
      const zoomChanged = zoom !== zoomRef.current;
      zoomRef.current = zoom;
      if (!mode.current.follow || mode.current.drawing) {
        if (zoomChanged) void load(dataQuery, zoom);
        return;
      }
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        if (!mode.current.follow || mode.current.drawing) return;
        const next = withParam(paramsRef.current, "bbox", formatBbox(bbox));
        if (next === toApiQuery(paramsRef.current)) {
          if (zoomChanged) void load(dataQuery, zoom);
          return;
        }
        navigate(next);
      }, 450);
    },
    [navigate, load, dataQuery],
  );

  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  /** Drop a viewport (`bbox`) update still waiting in the debounce. */
  function cancelViewportUpdate() {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }

  function startDrawing() {
    // A pan just before "Draw area" must not move the URL to that viewport
    // while the user is drawing (or replace the area they then finish).
    cancelViewportUpdate();
    mode.current = { ...mode.current, drawing: true };
    setDrawing([]);
  }

  function cancelDrawing() {
    mode.current = { ...mode.current, drawing: false };
    setDrawing(null);
  }

  function finishDrawing() {
    if (!drawing || drawing.length < 3) return;
    cancelViewportUpdate();
    const next: RawParams = { ...paramsRef.current, polygon: formatPolygon(drawing) };
    for (const key of ["bbox", "page", "near_lat", "near_lon", "radius_km"]) delete next[key];
    mode.current = { follow: false, drawing: false };
    setDrawing(null);
    setFollowMap(false);
    navigate(toApiQuery(next));
  }

  function clearArea() {
    cancelViewportUpdate();
    const next: RawParams = { ...paramsRef.current };
    for (const key of ["polygon", "near_lat", "near_lon", "radius_km", "page"]) delete next[key];
    mode.current = { ...mode.current, follow: true };
    setFollowMap(true);
    navigate(toApiQuery(next));
  }

  function nearMe() {
    setGeoError(false);
    if (!("geolocation" in navigator)) {
      setGeoError(true);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const next: RawParams = {
          ...paramsRef.current,
          near_lat: coords.latitude.toFixed(5),
          near_lon: coords.longitude.toFixed(5),
          radius_km: "3",
        };
        for (const key of ["bbox", "polygon", "page"]) delete next[key];
        cancelViewportUpdate();
        mode.current = { ...mode.current, follow: false };
        setFollowMap(false);
        setFocusBbox(bboxAround(coords.longitude, coords.latitude, 3));
        navigate(toApiQuery(next));
      },
      () => setGeoError(true),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
    );
  }

  function togglePlaces(key: string) {
    setPlaceGroups((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const onSelect = useCallback((id: string | null, props?: Record<string, unknown>) => {
    setHighlightId(id);
    setSelected(id && props ? props : null);
  }, []);

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
  const nearLat = Number(first(params.near_lat));
  const nearLon = Number(first(params.near_lon));
  const startBbox = polygon
    ? polygonBbox(polygon)
    : Number.isFinite(nearLat) && Number.isFinite(nearLon) && nearActive
      ? bboxAround(nearLon, nearLat, Number(first(params.radius_km)) || 3)
      : (parseBbox(first(params.bbox)) ?? initialBbox);
  const listOpen = view === "list";
  const footnotes = (
    <div className="flex flex-col gap-1 text-[11.5px] leading-relaxed text-ink-3">
      {error && <p className="text-danger">{m.error}</p>}
      {clustered && <p>{m.clustered}</p>}
      <p>
        {m.priceBubbles} {m.hiddenNotOnMap}
      </p>
      {pois && pois.features.length > 0 && (
        <p>
          {m.placesSource}. {m.placesDemoNote}
        </p>
      )}
      {sources.length > 0 && (
        <p>
          {m.boundarySource}: {sources.join(" · ")}
          {demoBoundary && <strong className="ms-1 text-warning">({m.demoBoundary})</strong>}
        </p>
      )}
    </div>
  );

  // Map-first stage: the map fills the space; everything else floats above it.
  //   start side  — results rail (desktop) / bottom sheet (phones, tablets)
  //   end side    — map tools (layers, draw, near me) as a floating column
  //   bottom      — the selected listing or project, centred in the open map
  return (
    <div className="relative size-full overflow-hidden">
      <div className="absolute inset-0">
        <PropertyMap
          bleed
          config={config}
          dict={dict}
          locale={locale}
          initialBbox={startBbox}
          data={data}
          boundaries={boundaries}
          showBoundaries={showAreas}
          pois={pois}
          satellite={satellite}
          development={future ? projects : null}
          onSelectProject={setProject}
          polygon={polygon}
          drawing={drawing}
          highlightId={highlightId}
          focusBbox={focusBbox}
          onViewportChange={onViewportChange}
          onSelect={onSelect}
          onDrawPoint={(p) => setDrawing((d) => (d ? [...d, p] : d))}
        />
      </div>

      {/* Status pills (drawing hint, location errors) float at the top centre. */}
      {(drawing || geoError) && (
        <div className="pointer-events-none absolute inset-x-4 top-[calc(var(--map-top)+0.75rem)] z-[var(--z-float)] flex justify-center">
          <p
            role="status"
            className={`surface-float pop-in pointer-events-auto max-w-md rounded-full px-4 py-2 text-center text-[13px] ${geoError ? "text-danger" : "text-ink"}`}
          >
            {geoError ? m.nearMeDenied : m.drawHint}
          </p>
        </div>
      )}

      {/* Results: a rail on wide screens, a bottom sheet on phones and tablets. */}
      <section
        aria-label={m.showList}
        className={`surface-modal absolute z-[var(--z-float)] flex flex-col overflow-hidden transition-[height] duration-[var(--duration-spatial)] ease-[var(--ease-spring)] max-lg:inset-x-2 max-lg:bottom-2 max-lg:rounded-[1.5rem] lg:start-4 lg:top-[calc(var(--map-top)+0.75rem)] lg:bottom-4 lg:w-[392px] lg:rounded-[var(--radius-card)] ${
          listOpen ? "max-lg:h-[72%]" : "max-lg:h-auto"
        } ${selected || project ? "max-lg:hidden" : ""}`}
      >
        <header className="flex shrink-0 flex-col gap-2 px-4 pt-2 pb-3 lg:pt-4">
          {/* Sheet handle (phones/tablets): tap to open or close the list. */}
          <button
            type="button"
            onClick={() => setView(listOpen ? "map" : "list")}
            aria-expanded={listOpen}
            aria-label={listOpen ? m.showMap : m.showList}
            className="mx-auto mb-1 flex h-5 w-full items-center justify-center lg:hidden"
          >
            <span aria-hidden className="h-1 w-10 rounded-full bg-hairline-strong" />
          </button>
          <div className="flex items-baseline justify-between gap-3">
            <h1 className="font-display text-lg font-semibold tracking-tight text-ink">
              {m.title}
            </h1>
            <p className="text-[13px] text-ink-3 tabular" data-testid="map-total">
              <span className="font-semibold text-ink">{total}</span> {m.inView}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-[13px] text-ink-2">
              <input
                type="checkbox"
                checked={followMap}
                disabled={!!polygon || nearActive || !!drawing}
                onChange={(e) => {
                  const follow = e.target.checked;
                  mode.current = { ...mode.current, follow };
                  if (!follow) cancelViewportUpdate();
                  setFollowMap(follow);
                }}
                className="size-4 accent-[var(--accent)]"
              />
              {m.searchAsMove}
            </label>
            {(polygon || nearActive) && !drawing && (
              <button type="button" onClick={clearArea} className="chip ms-auto" data-active="true">
                {nearActive ? `${m.nearMeActive} · ${m.clearNear}` : m.clearArea}
                <Icon name="close" className="size-3.5" />
              </button>
            )}
          </div>
          {filters && (
            <details className="group">
              <summary className="chip w-fit cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                <Icon name="filter" className="size-4" />
                {dict.search.filters}
                <Icon
                  name="chevron-down"
                  className="size-3.5 transition-transform duration-[var(--duration-base)] group-open:rotate-180"
                />
              </summary>
              <div className="fade-in quiet-scroll mt-3 max-h-[40vh] overflow-y-auto pe-1">
                {filters}
              </div>
            </details>
          )}
        </header>

        <div
          className={`quiet-scroll flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto border-t border-hairline px-2 py-2 ${
            listOpen ? "" : "max-lg:hidden"
          }`}
        >
          {items.length === 0 && <EmptyState title={dict.search.noResults} glyph="map" />}
          <ul className="flex flex-col">
            {items.map((card, i) => {
              const title = locale === "en" && card.title_en ? card.title_en : card.title_ar;
              const active = highlightId === card.id;
              return (
                <li key={card.id} className="reveal" style={stagger(i)}>
                  <a
                    href={`/properties/${card.id}`}
                    onMouseEnter={() => setHighlightId(card.id)}
                    onMouseLeave={() => setHighlightId(selected ? String(selected.id) : null)}
                    onFocus={() => setHighlightId(card.id)}
                    aria-current={active ? "true" : undefined}
                    className={`flex gap-3 rounded-2xl p-2 transition-colors duration-[var(--duration-quick)] ${active ? "bg-accent-tint" : "hover:bg-fill"}`}
                  >
                    {card.cover_url ? (
                      <SafeImage
                        src={card.cover_url}
                        alt=""
                        fallbackLabel="—"
                        className="h-[72px] w-24 shrink-0 rounded-xl bg-fill object-cover"
                      />
                    ) : (
                      <div className="grid h-[72px] w-24 shrink-0 place-items-center rounded-xl bg-fill text-ink-3">
                        <Icon name="home" className="size-5 opacity-70" />
                      </div>
                    )}
                    <div className="flex min-w-0 flex-col gap-0.5 text-sm">
                      <span className="font-display font-semibold tracking-tight text-ink tabular">
                        {priceLabel(card, dict, locale)}
                      </span>
                      <span className="truncate text-ink-2">{title}</span>
                      <span className="flex min-w-0 items-center gap-1 text-xs text-ink-3">
                        <Icon name="pin" className="size-3 shrink-0 text-spatial" />
                        <span className="truncate">
                          {[placeName(card.district ?? null, locale), placeName(card.city, locale)]
                            .filter(Boolean)
                            .join("، ")}
                          {card.area_m2 ? ` · ${formatArea(card.area_m2, locale)}` : ""}
                        </span>
                      </span>
                      {card.is_demo && (
                        <span>
                          <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                        </span>
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
              className="press mx-auto inline-flex h-9 items-center gap-1.5 rounded-full px-4 text-sm font-medium text-accent hover:bg-accent-tint"
            >
              {dict.landing.viewAll}
              <Icon name="arrow" className="size-4" />
            </a>
          )}
          <div className="mt-auto px-2 pt-3 pb-1">{footnotes}</div>
        </div>
      </section>

      {/* Map tools: a floating column on the end side. */}
      <div className="absolute end-3 top-[calc(var(--map-top)+0.75rem)] z-[var(--z-float)] flex flex-col items-end gap-2 lg:end-4">
        <details className="group relative" data-testid="map-layers">
          <summary className="press surface-float flex h-10 cursor-pointer list-none items-center gap-2 rounded-full px-3.5 text-sm font-medium text-ink [&::-webkit-details-marker]:hidden">
            <Icon name="layers" className="size-[18px] text-spatial" />
            <span className="max-sm:sr-only">{m.layers}</span>
          </summary>
          <div className="surface-focus pop-in absolute end-0 top-12 flex w-72 origin-top-right flex-col gap-4 rounded-[var(--radius-card)] p-4 text-sm rtl:origin-top-left">
            {config.satellite && (
              <div className="seg w-full" role="group">
                {[false, true].map((sat) => (
                  <button
                    key={String(sat)}
                    type="button"
                    aria-pressed={satellite === sat}
                    onClick={() => setSatellite(sat)}
                    className="flex-1"
                  >
                    {sat ? m.satellite : m.streets}
                  </button>
                ))}
              </div>
            )}
            <label className="flex items-center justify-between gap-2 text-ink">
              <span className="flex items-center gap-2">
                <span aria-hidden className="size-2.5 rounded-full bg-gold-500" />
                {dict.future.layer}
              </span>
              <input
                type="checkbox"
                data-layer="future"
                checked={future}
                onChange={(e) => {
                  setFuture(e.target.checked);
                  if (!e.target.checked) setProject(null);
                }}
                className="size-4 accent-[var(--accent)]"
              />
            </label>
            <label className="flex items-center justify-between gap-2 text-ink">
              {m.areas}
              <input
                type="checkbox"
                checked={showAreas}
                onChange={(e) => setShowAreas(e.target.checked)}
                className="size-4 accent-[var(--accent)]"
              />
            </label>
            <fieldset className="flex flex-col gap-2 border-t border-hairline pt-3">
              <legend className="meta mb-2 font-medium">{m.places}</legend>
              <div className="flex flex-wrap gap-1.5">
                {PLACE_GROUPS.map((g) => (
                  <button
                    key={g.key}
                    type="button"
                    data-place={g.key}
                    aria-pressed={placeGroups.has(g.key)}
                    onClick={() => togglePlaces(g.key)}
                    className="chip chip-spatial"
                  >
                    <span
                      aria-hidden
                      className="size-2 rounded-full"
                      style={{ background: POI_COLORS[g.key] }}
                    />
                    {dict.nearby.categories[g.key as keyof typeof dict.nearby.categories]}
                  </button>
                ))}
              </div>
              {placeGroups.size > 0 && !placesAllowed(viewport) && (
                <p className="meta">{m.zoomInForPlaces}</p>
              )}
            </fieldset>
          </div>
        </details>

        {drawing ? (
          <div className="surface-float pop-in flex items-center gap-1 rounded-full p-1">
            <Button
              size="sm"
              onClick={finishDrawing}
              disabled={drawing.length < 3}
              data-testid="finish-area"
            >
              <Icon name="check" className="size-4" />
              {m.finishDrawing}
            </Button>
            <Button size="sm" variant="ghost" onClick={cancelDrawing}>
              {m.cancelDrawing}
            </Button>
          </div>
        ) : (
          <>
            <Button variant="glass" className="h-10" onClick={startDrawing} data-testid="draw-area">
              <Icon name="draw" className="size-[18px] text-spatial" />
              <span className="max-sm:sr-only">{m.drawArea}</span>
            </Button>
            <Button variant="glass" className="h-10" onClick={nearMe}>
              <Icon name="locate" className="size-[18px] text-spatial" />
              <span className="max-sm:sr-only">{m.nearMe}</span>
            </Button>
          </>
        )}
      </div>

      {project && (
        <ProjectSheet
          props={project}
          dict={dict}
          locale={locale}
          onClose={() => setProject(null)}
        />
      )}
      {selected && !project && (
        <SelectionSheet
          props={selected}
          dict={dict}
          locale={locale}
          onClose={() => onSelect(null)}
        />
      )}
    </div>
  );
}

/** A Future Iraq project over the map, always with its source and date. */
function ProjectSheet({
  props,
  dict,
  locale,
  onClose,
}: {
  props: Record<string, unknown>;
  dict: Dictionary;
  locale: Locale;
  onClose: () => void;
}) {
  const f = dict.future;
  const name = String((locale === "en" && props.name_en) || props.name_ar || "");
  // MapLibre serialises array properties to JSON strings.
  const sources: string[] = (() => {
    const raw = props.sources;
    if (Array.isArray(raw)) return raw.map(String);
    try {
      return typeof raw === "string" ? (JSON.parse(raw) as string[]) : [];
    } catch {
      return [];
    }
  })();
  return (
    <div
      role="dialog"
      aria-label={name}
      data-testid="map-project"
      className="pointer-events-none absolute inset-x-2 bottom-2 z-[var(--z-float)] flex justify-center lg:start-[calc(392px+2rem)] lg:end-4 lg:bottom-4"
    >
      <div className="surface-focus pop-in pointer-events-auto flex w-full max-w-md flex-col gap-2.5 rounded-[var(--radius-card)] p-4 text-sm">
        <div className="flex items-start justify-between gap-3">
          <p className="font-display text-base font-semibold text-ink">{name}</p>
          <button
            type="button"
            onClick={onClose}
            aria-label={dict.map.close}
            className="icon-btn size-8 shrink-0"
          >
            <Icon name="close" className="size-4" />
          </button>
        </div>
        <p className="flex flex-wrap gap-1.5">
          <TrustBadge kind="source">
            {(f.statuses as Record<string, string>)[String(props.status)] ?? String(props.status)}
          </TrustBadge>
          <TrustBadge kind="estimate">
            {f.precision[String(props.location_precision) as keyof typeof f.precision]}
          </TrustBadge>
        </p>
        <p className="text-xs text-ink-3">
          {dict.intel.source}: {sources.join(" · ")} ·{" "}
          {props.latest_source_date ? String(props.latest_source_date) : f.undated}
        </p>
        <Link
          href={`/future#${encodeURIComponent(String(props.slug))}`}
          className="font-medium text-accent underline-offset-4 hover:underline"
        >
          {f.evidence}
        </Link>
      </div>
    </div>
  );
}

/** The selected listing as a glass card over the map (replaces map popups). */
function SelectionSheet({
  props,
  dict,
  locale,
  onClose,
}: {
  props: Record<string, unknown>;
  dict: Dictionary;
  locale: Locale;
  onClose: () => void;
}) {
  const id = String(props.id);
  const title = String((locale === "en" && props.title_en) || props.title_ar || "");
  const period =
    typeof props.rent_period === "string" && props.rent_period
      ? ` ${dict.property.perPeriod[props.rent_period as keyof typeof dict.property.perPeriod] ?? ""}`
      : "";
  const price =
    props.price_on_request === true || props.price_amount == null
      ? dict.listing.priceOnRequest
      : `${formatCompactPrice(String(props.price_amount), props.currency === "USD" ? "USD" : "IQD", locale) ?? ""}${period}`;
  const cover = typeof props.cover_url === "string" ? props.cover_url : null;
  return (
    <div
      role="dialog"
      aria-label={title}
      data-testid="map-selection"
      className="pointer-events-none absolute inset-x-2 bottom-2 z-[var(--z-float)] flex justify-center lg:start-[calc(392px+2rem)] lg:end-4 lg:bottom-4"
    >
      {/* Keyed by listing: choosing another property replays the arrival. */}
      <div
        key={id}
        className="surface-focus pop-in pointer-events-auto flex w-full max-w-md gap-3.5 rounded-[var(--radius-card)] p-2.5"
      >
        <div className="relative size-28 shrink-0 overflow-hidden rounded-[calc(var(--radius-card)-0.5rem)] bg-fill">
          {cover ? (
            <SafeImage src={cover} alt="" fallbackLabel="—" className="size-full object-cover" />
          ) : (
            <span className="grid size-full place-items-center text-ink-3">
              <Icon name="home" className="size-6 opacity-70" />
            </span>
          )}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1 py-1 text-sm">
          <p className="font-display text-lg font-semibold tracking-tight text-ink tabular">
            {price}
          </p>
          <p className="line-clamp-2 leading-snug text-ink-2">{title}</p>
          <div className="flex flex-wrap gap-1">
            {props.is_demo === true && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
            {props.approximate === true && (
              <TrustBadge kind="estimate">{dict.map.approximate}</TrustBadge>
            )}
          </div>
          <Link
            href={`/properties/${encodeURIComponent(id)}`}
            className="press mt-auto inline-flex h-8 w-fit items-center gap-1.5 rounded-full bg-accent-fill px-3.5 text-[13px] font-medium text-on-accent hover:bg-accent-fill-hover"
          >
            {dict.map.openListing}
            <Icon name="arrow" className="size-3.5" />
          </Link>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={dict.map.close}
          className="icon-btn size-8 shrink-0"
        >
          <Icon name="close" className="size-4" />
        </button>
      </div>
    </div>
  );
}
