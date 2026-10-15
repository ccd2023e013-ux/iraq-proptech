"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";

import { Button } from "@/components/ui/Button";
import { Icon, type IconName } from "@/components/ui/Icon";
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
import { canTransition, isPlainClick, navigateWithTransition } from "@/lib/viewTransition";
import { type MapConfig, parseBbox } from "@/lib/map/provider";
import { type RawParams, first, toApiQuery, withParam } from "@/lib/search";
import type { PropertyCard } from "@/types/property";

import {
  type FocusRequest,
  type MapFeatureCollection,
  POI_COLORS,
  PropertyMap,
} from "./PropertyMap";
import type { Feature, FeatureCollection, Point } from "geojson";

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

/** Phone sheet positions: just the header, half the map, or nearly all of it. */
type Sheet = "peek" | "half" | "full";
const SHEET_SHARE: Record<Sheet, number> = { peek: 0, half: 0.52, full: 0.9 };

/** The selection card's data, from a map feature or a list card. */
function cardProps(card: PropertyCard): Record<string, unknown> {
  return {
    id: card.id,
    title_ar: card.title_ar,
    title_en: card.title_en,
    price_amount: card.price_amount,
    currency: card.currency,
    price_on_request: card.price_on_request,
    rent_period: card.rent_period,
    cover_url: card.cover_url,
    is_demo: card.is_demo,
    area_m2: card.area_m2,
  };
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
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  const [sheet, setSheet] = useState<Sheet>("peek");
  const [placeGroups, setPlaceGroups] = useState<Set<string>>(new Set());
  const [showAreas, setShowAreas] = useState(true);
  const [satellite, setSatellite] = useState(false);
  const [buildings3d, setBuildings3d] = useState(false);
  const [loadedPois, setPois] = useState<FeatureCollection | null>(null);
  const [future, setFuture] = useState(first(params.layer) === "future");
  const [projects, setProjects] = useState<FeatureCollection | null>(null);
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [viewport, setViewport] = useState<Bbox | null>(null);
  const [zoom, setZoom] = useState(12);
  const [focusBbox, setFocusBbox] = useState<Bbox | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [navigating, startNavigation] = useTransition();
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

  // `?selected=<id>` (from a property page's "Open on the map"): select that
  // listing once its point is loaded, and glide to it.
  const selectedApplied = useRef<string | null>(null);
  const load = useCallback(async (query: string, zoom: number) => {
    setLoadingData(true);
    try {
      const sep = query ? "&" : "";
      const result = await apiFetch<MapFeatureCollection>(
        `/api/v1/map/properties?${query}${sep}zoom=${zoom}`,
      );
      setData(result);
      setError(false);
      const wanted = first(paramsRef.current.selected);
      if (wanted && selectedApplied.current !== wanted) {
        const hit = result.features.find(
          (f) => f.geometry.type === "Point" && String(f.properties?.id) === wanted,
        );
        if (hit) {
          selectedApplied.current = wanted;
          const [lon, lat] = (hit.geometry as Point).coordinates as [number, number];
          setSelected((hit.properties ?? {}) as Record<string, unknown>);
          setFocusRequest((r) => ({ id: wanted, lon, lat, n: (r?.n ?? 0) + 1 }));
        }
      }
    } catch {
      setError(true);
    } finally {
      setLoadingData(false);
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
    (query: string) =>
      startNavigation(() =>
        router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false }),
      ),
    [router, pathname],
  );

  const onViewportChange = useCallback(
    (bbox: Bbox, zoom: number) => {
      setViewport(bbox);
      setZoom(zoom);
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

  // The layers panel closes like a popover: on a tap outside it or on Escape.
  const layersRef = useRef<HTMLDetailsElement>(null);
  const [layersOpen, setLayersOpen] = useState(false);
  useEffect(() => {
    const close = (event: Event) => {
      const panel = layersRef.current;
      if (!panel?.open) return;
      if (event instanceof KeyboardEvent) {
        if (event.key !== "Escape") return;
      } else if (panel.contains(event.target as Node)) {
        return;
      }
      panel.open = false;
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);

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
    setSelected(null);
    goSheet("peek");
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
    setSelected(id && props ? props : null);
    if (id) setProject(null);
  }, []);

  /** "Show on map" from the list: select the listing and glide to it. */
  function showOnMap(card: PropertyCard) {
    if (!card.display_location) return;
    setSelected(cardProps(card));
    setProject(null);
    goSheet("peek");
    setFocusRequest((r) => ({
      id: card.id,
      lon: card.display_location!.lon,
      lat: card.display_location!.lat,
      n: (r?.n ?? 0) + 1,
    }));
  }

  // Phone sheet: drag the header between peek, half and full; tap toggles.
  const sheetRef = useRef<HTMLElement>(null);
  const drag = useRef<{ y: number; start: number; t: number; moved: boolean } | null>(null);
  function sheetOffset(target: Sheet): number {
    const el = sheetRef.current;
    const parent = el?.parentElement;
    if (!el || !parent) return 0;
    const full = el.offsetHeight;
    const header = el.querySelector("header")?.offsetHeight ?? 120;
    const visible = target === "peek" ? header : parent.clientHeight * SHEET_SHARE[target];
    return Math.max(0, full - visible);
  }
  function onSheetPointerDown(event: ReactPointerEvent) {
    if (window.matchMedia("(min-width: 768px)").matches) return;
    if ((event.target as Element).closest("input,select,label,details,a")) return;
    drag.current = {
      y: event.clientY,
      start: sheetOffset(sheet),
      t: event.timeStamp,
      moved: false,
    };
  }
  function onSheetPointerMove(event: ReactPointerEvent) {
    const d = drag.current;
    const el = sheetRef.current;
    if (!d || !el) return;
    const dy = event.clientY - d.y;
    if (!d.moved && Math.abs(dy) < 6) return;
    if (!d.moved) (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
    d.moved = true;
    el.style.transition = "none";
    el.style.transform = `translateY(${Math.max(0, d.start + dy)}px)`;
  }
  function onSheetPointerUp(event: ReactPointerEvent) {
    const d = drag.current;
    drag.current = null;
    const el = sheetRef.current;
    if (!d || !el || !d.moved) return;
    el.style.transition = "";
    el.style.transform = "";
    const dy = event.clientY - d.y;
    const velocity = dy / Math.max(1, event.timeStamp - d.t); // px per ms
    const at = d.start + dy;
    const order: Sheet[] = ["full", "half", "peek"];
    let next: Sheet;
    if (Math.abs(velocity) > 0.5) {
      const i = order.indexOf(sheet) + (velocity > 0 ? 1 : -1);
      next = order[Math.min(Math.max(i, 0), order.length - 1)]!;
    } else {
      next = order.reduce((best, s) =>
        Math.abs(sheetOffset(s) - at) < Math.abs(sheetOffset(best) - at) ? s : best,
      );
    }
    goSheet(next);
  }
  // The sheet's resting offset (px), measured from the DOM in event handlers
  // and after layout; before the first measurement CSS approximates "peek".
  const [sheetY, setSheetY] = useState("calc(100% - 7.5rem)");
  const sheetNow = useRef<Sheet>("peek");
  function goSheet(next: Sheet) {
    sheetNow.current = next;
    setSheet(next);
    setSheetY(`${sheetOffset(next)}px`);
  }
  // The header itself changes height between positions: settle on the new one.
  useEffect(() => {
    const frame = requestAnimationFrame(() => setSheetY(`${sheetOffset(sheetNow.current)}px`));
    return () => cancelAnimationFrame(frame);
  }, [sheet]);
  useEffect(() => {
    const measure = () => setSheetY(`${sheetOffset(sheetNow.current)}px`);
    const frame = requestAnimationFrame(measure);
    window.addEventListener("resize", measure);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", measure);
    };
  }, [items.length, total]);

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
  const busy = loadingData || navigating;
  // No area asked for (no link, drawing, place or "near me"): open on where the
  // listings actually are inside the launch area, not on the whole box.
  const fitToData =
    !polygon &&
    !nearActive &&
    !first(params.bbox) &&
    !first(params.city_id) &&
    !first(params.governorate_id) &&
    !first(params.district_id);
  const hideSheet = !!(selected || project);
  const sheetOpen = sheet !== "peek";
  const selectedId = selected ? String(selected.id) : null;
  const footnotes = (
    <div className="flex flex-col gap-1.5 text-[11.5px] leading-relaxed text-ink-3">
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
      {buildings3d && <p>{m.buildings3dNote}</p>}
    </div>
  );

  // Map-first stage: the map fills the space.
  //   start side  — results: a docked rail (wide screens) / a bottom sheet (phones)
  //   end side    — one instrument column (layers, draw, near me, 3D)
  //   bottom      — the selected listing or project, in the open part of the map
  return (
    <div className="relative size-full overflow-hidden [--rail:0px] md:[--rail:340px] lg:[--rail:400px]">
      <div className="absolute inset-0">
        <PropertyMap
          bleed
          fitToData={fitToData}
          config={config}
          dict={dict}
          locale={locale}
          initialBbox={startBbox}
          data={data}
          boundaries={boundaries}
          showBoundaries={showAreas}
          pois={pois}
          satellite={satellite}
          buildings3d={buildings3d}
          development={future ? projects : null}
          onSelectProject={setProject}
          polygon={polygon}
          drawing={drawing}
          selectedId={selectedId}
          highlightId={highlightId}
          focusRequest={focusRequest}
          focusBbox={focusBbox}
          onViewportChange={onViewportChange}
          onSelect={onSelect}
          onDrawPoint={(p) => setDrawing((d) => (d ? [...d, p] : d))}
        />
      </div>

      {/* Drawing and location status float at the top centre of the open map. */}
      {(drawing || geoError) && (
        <div className="pointer-events-none absolute inset-x-4 top-[calc(var(--map-top)+0.75rem)] z-[var(--z-float)] flex justify-center md:start-[calc(var(--rail)+1rem)]">
          <div
            role="status"
            className={`surface-float pop-in pointer-events-auto flex max-w-md items-center gap-3 rounded-[var(--radius-control)] px-3.5 py-2 text-[13px] ${geoError ? "text-danger" : "text-ink"}`}
          >
            {geoError ? (
              m.nearMeDenied
            ) : (
              <>
                <span aria-hidden className="relative grid size-5 place-items-center">
                  <span className="absolute inset-0 animate-ping rounded-full bg-spatial-fill/30" />
                  <span className="size-2 rounded-full bg-spatial-fill" />
                </span>
                <span>{m.drawHint}</span>
                <span className="caption shrink-0 tabular">
                  {m.drawPoints.replace("{n}", String(drawing?.length ?? 0))}
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Results: a docked rail on tablets and wide screens, a draggable sheet
          on phones. One surface with the map: its rows mirror the map's tags
          (hover a row → the tag lifts; "show on map" → the camera glides). */}
      <section
        ref={sheetRef}
        aria-label={m.results}
        data-map-rail
        data-sheet={sheet}
        style={{ "--sheet-y": hideSheet ? "110%" : sheetY } as CSSProperties}
        className="absolute z-[var(--z-float)] flex flex-col overflow-hidden transition-transform duration-[var(--duration-spatial)] ease-[var(--ease-standard)] max-md:inset-x-0 max-md:bottom-0 max-md:h-[90%] max-md:translate-y-[var(--sheet-y)] max-md:rounded-t-[var(--radius-sheet)] max-md:bg-raised/95 max-md:shadow-[0_-12px_40px_-16px_rgb(0_0_0/0.6)] max-md:backdrop-blur-xl md:start-0 md:top-[var(--map-top)] md:bottom-0 md:w-[var(--rail)] md:border-e md:border-hairline md:bg-canvas/95 md:backdrop-blur-xl"
      >
        {/* A thin progress line while results update; the map stays usable. */}
        <div
          aria-hidden
          className={`pointer-events-none absolute inset-x-0 top-0 h-0.5 overflow-hidden transition-opacity duration-[var(--duration-base)] ${busy ? "opacity-100" : "opacity-0"}`}
        >
          <div className="map-progress h-full w-1/3 bg-spatial-fill" />
        </div>
        <header
          className="flex shrink-0 touch-none flex-col gap-3 px-4 pt-2 pb-3 select-none md:touch-auto md:px-5 md:pt-5 md:select-auto"
          onPointerDown={onSheetPointerDown}
          onPointerMove={onSheetPointerMove}
          onPointerUp={onSheetPointerUp}
          onPointerCancel={onSheetPointerUp}
        >
          {/* Sheet handle (phones): tap to open or close the list, or drag. */}
          <button
            type="button"
            onClick={() => goSheet(sheetOpen ? "peek" : "half")}
            aria-expanded={sheetOpen}
            aria-label={sheetOpen ? m.showMap : m.showList}
            data-testid="sheet-handle"
            className="mx-auto -mb-1 flex h-6 w-20 items-center justify-center md:hidden"
          >
            <span aria-hidden className="h-1 w-10 rounded-full bg-hairline-strong" />
          </button>
          <div className="flex items-end justify-between gap-3">
            <div className="flex min-w-0 items-baseline gap-2">
              <h1 className="sr-only">{m.title}</h1>
              <p className="kpi text-[1.75rem] leading-none text-ink" data-testid="map-total">
                {total}
                <span className="sr-only"> {m.inView}</span>
              </p>
              <p aria-hidden className="meta">
                {m.inViewShort}
              </p>
            </div>
            <p
              role="status"
              aria-live="polite"
              className={`caption flex shrink-0 items-center gap-1.5 transition-opacity duration-[var(--duration-base)] ${busy ? "opacity-100" : "opacity-0"}`}
            >
              <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-spatial-fill" />
              {busy ? m.updating : ""}
            </p>
          </div>
          {/* Phones at peek show only the count: the map stays open. */}
          <div
            className={`flex flex-col gap-3 ${sheet === "peek" && !polygon && !nearActive ? "max-md:hidden" : ""}`}
          >
            <div className="flex items-center justify-between gap-2">
              <div role="group" aria-label={dict.property.purpose} className="seg">
                {(["", "SALE", "RENT"] as const).map((value) => (
                  <button
                    key={value || "all"}
                    type="button"
                    aria-pressed={(first(params.purpose) ?? "") === value}
                    onClick={() => navigate(withParam(paramsRef.current, "purpose", value))}
                    className="!h-8 !px-3 !text-[13px]"
                  >
                    {value ? dict.listing.purposes[value] : m.allPurposes}
                  </button>
                ))}
              </div>
              <label className="flex min-w-0 items-center gap-2">
                <span className="sr-only">{m.sortBy}</span>
                <select
                  value={first(params.sort) ?? "newest"}
                  onChange={(e) => navigate(withParam(paramsRef.current, "sort", e.target.value))}
                  className="field h-9 w-auto min-w-0 bg-fill pe-8 text-[13px] shadow-none"
                >
                  {(["newest", "price_asc", "price_desc", "area_desc"] as const).map((sort) => (
                    <option key={sort} value={sort}>
                      {dict.search.sorts[sort]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex cursor-pointer items-center gap-2.5 text-[13px] text-ink-2">
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
                  className="peer sr-only"
                />
                <span
                  aria-hidden
                  className="relative h-5 w-9 shrink-0 rounded-full bg-fill-strong transition-colors duration-[var(--duration-quick)] peer-checked:bg-accent-fill peer-focus-visible:ring-2 peer-focus-visible:ring-accent peer-disabled:opacity-40 after:absolute after:start-0.5 after:top-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition-transform after:duration-[var(--duration-base)] peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4"
                />
                {m.searchAsMove}
              </label>
              {(polygon || nearActive) && !drawing && (
                <button
                  type="button"
                  onClick={clearArea}
                  className="chip ms-auto"
                  data-active="true"
                >
                  {nearActive ? `${m.nearMeActive} · ${m.clearNear}` : m.clearArea}
                  <Icon name="close" className="size-3.5" />
                </button>
              )}
            </div>
            {filters && (
              <details className="group" onToggle={(e) => e.currentTarget.open && goSheet("full")}>
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
          </div>
        </header>

        <div
          className={`quiet-scroll flex min-h-0 flex-1 flex-col overflow-y-auto border-t border-hairline transition-opacity duration-[var(--duration-base)] ${busy ? "opacity-70" : ""}`}
        >
          {items.length === 0 && (
            <div className="flex flex-col items-start gap-3 px-5 py-8">
              <span className="grid size-11 place-items-center rounded-full bg-fill text-spatial">
                <Icon name="map" className="size-5" />
              </span>
              <p className="max-w-[18rem] text-[15px] leading-relaxed text-ink-2">{m.noneInView}</p>
            </div>
          )}
          <ul className="flex flex-col gap-0.5 py-2">
            {items.map((card) => {
              const title = locale === "en" && card.title_en ? card.title_en : card.title_ar;
              const active = highlightId === card.id || selectedId === card.id;
              const area = formatArea(card.area_m2, locale);
              const where = [placeName(card.district ?? null, locale), placeName(card.city, locale)]
                .filter(Boolean)
                .join("، ");
              return (
                <li key={card.id}>
                  <div
                    data-active={active || undefined}
                    className="group relative mx-2 flex items-center gap-1 rounded-[var(--radius-control)] transition-colors duration-[var(--duration-quick)] hover:bg-fill/70 data-[active]:bg-accent-tint/60"
                  >
                    <span
                      aria-hidden
                      className="absolute inset-y-3 -start-2 w-[3px] origin-center scale-y-0 rounded-full bg-accent-fill transition-transform duration-[var(--duration-base)] ease-[var(--ease-standard)] group-data-[active]:scale-y-100"
                    />
                    <a
                      href={`/properties/${card.id}`}
                      onMouseEnter={() => setHighlightId(card.id)}
                      onMouseLeave={() => setHighlightId(null)}
                      onFocus={() => setHighlightId(card.id)}
                      onBlur={() => setHighlightId(null)}
                      aria-current={selectedId === card.id ? "true" : undefined}
                      className="flex min-w-0 flex-1 gap-3.5 p-2"
                    >
                      <span className="relative aspect-[4/3] w-[104px] shrink-0 overflow-hidden rounded-[10px] bg-fill">
                        {card.cover_url ? (
                          <SafeImage
                            src={card.cover_url}
                            alt=""
                            fallbackLabel="—"
                            className="photo size-full object-cover transition-transform duration-[var(--duration-slow)] ease-[var(--ease-standard)] group-hover:scale-[1.04]"
                          />
                        ) : (
                          <span className="grid size-full place-items-center text-ink-3">
                            <Icon name="home" className="size-5 opacity-70" />
                          </span>
                        )}
                        {card.is_demo && (
                          <span className="absolute start-0 bottom-0 rounded-se-[6px] bg-gold-500 px-1.5 py-px text-[10px] font-semibold text-[#1d1405]">
                            {dict.listing.demo}
                          </span>
                        )}
                      </span>
                      <span className="flex min-w-0 flex-col justify-center gap-1">
                        <span className="flex min-w-0 items-baseline gap-2">
                          <span className="kpi truncate text-[17px] text-ink">
                            {priceLabel(card, dict, locale)}
                          </span>
                          <span className="caption shrink-0">
                            {dict.listing.purposes[card.purpose]}
                          </span>
                        </span>
                        <span className="truncate text-[13.5px] text-ink-2 group-hover:text-ink">
                          {title}
                        </span>
                        <span className="caption flex min-w-0 items-center gap-3 text-ink-3">
                          {where && (
                            <span className="flex min-w-0 items-center gap-1">
                              <Icon name="pin" className="size-3.5 shrink-0 text-spatial" />
                              <span className="truncate">{where}</span>
                            </span>
                          )}
                          {card.bedrooms != null && (
                            <span className="flex shrink-0 items-center gap-1 tabular">
                              <Icon name="bed" className="size-3.5" />
                              {card.bedrooms}
                            </span>
                          )}
                          {area && <span className="shrink-0 tabular">{area}</span>}
                        </span>
                      </span>
                    </a>
                    {card.display_location && (
                      <button
                        type="button"
                        onClick={() => showOnMap(card)}
                        aria-label={`${m.showOnMap}: ${title}`}
                        data-testid="show-on-map"
                        title={m.showOnMap}
                        className="icon-btn me-1 size-9 shrink-0 text-ink-3 opacity-60 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                      >
                        <Icon name="locate" className="size-[18px] text-spatial" />
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          {total > items.length && (
            <a
              href={`/properties?${toApiQuery(params)}`}
              className="link mx-5 mt-2 inline-flex w-fit items-center gap-1.5 text-sm font-medium"
            >
              {dict.landing.viewAll}
              <Icon name="arrow" className="size-4" />
            </a>
          )}
          <div className="mt-auto px-5 pt-5 pb-4">{footnotes}</div>
        </div>
      </section>

      {/* Instruments: one column on the end side. */}
      <div
        role="toolbar"
        aria-label={m.tools}
        aria-orientation="vertical"
        className="absolute end-3 top-[calc(var(--map-top)+0.75rem)] z-[var(--z-float)] flex flex-col items-end gap-2 lg:end-4"
      >
        <div className="surface-float flex flex-col rounded-[var(--radius-card)] p-1">
          <details
            ref={layersRef}
            className="group relative z-20"
            data-testid="map-layers"
            onToggle={(e) => setLayersOpen(e.currentTarget.open)}
          >
            <summary
              title={m.layers}
              aria-label={m.layers}
              className="list-none [&::-webkit-details-marker]:hidden"
            >
              <ToolFace icon="layers" active={layersOpen} />
            </summary>
            <LayerPanel
              dict={dict}
              hasSatellite={!!config.satellite}
              satellite={satellite}
              setSatellite={setSatellite}
              buildings3d={buildings3d}
              setBuildings3d={setBuildings3d}
              zoom={zoom}
              future={future}
              setFuture={(on) => {
                setFuture(on);
                if (!on) setProject(null);
              }}
              showAreas={showAreas}
              setShowAreas={setShowAreas}
              placeGroups={placeGroups}
              togglePlaces={togglePlaces}
              placesBlocked={placeGroups.size > 0 && !placesAllowed(viewport)}
            />
          </details>
          <span aria-hidden className="mx-2 h-px bg-hairline" />
          <button
            type="button"
            onClick={drawing ? cancelDrawing : startDrawing}
            aria-pressed={!!drawing}
            aria-label={m.drawArea}
            title={m.drawArea}
            data-testid={drawing ? undefined : "draw-area"}
          >
            <ToolFace icon="draw" active={!!drawing} />
          </button>
          <button type="button" onClick={nearMe} aria-label={m.nearMe} title={m.nearMe}>
            <ToolFace icon="locate" active={nearActive} />
          </button>
          <button
            type="button"
            onClick={() => setBuildings3d((v) => !v)}
            aria-pressed={buildings3d}
            aria-label={m.buildings3d}
            data-testid="buildings-3d"
            title={m.buildings3d}
          >
            <ToolFace icon="cube" active={buildings3d} />
          </button>
        </div>

        {drawing && (
          <div className="surface-float pop-in flex items-center gap-1 rounded-[var(--radius-control)] p-1">
            <Button
              size="sm"
              onClick={finishDrawing}
              disabled={drawing.length < 3}
              data-testid="finish-area"
              title={drawing.length < 3 ? m.drawNeedMore : undefined}
            >
              <Icon name="check" className="size-4" />
              {m.finishDrawing}
            </Button>
            <Button size="sm" variant="ghost" onClick={cancelDrawing}>
              {m.cancelDrawing}
            </Button>
          </div>
        )}
        {buildings3d && zoom < 13 && (
          <p className="surface-float pop-in caption max-w-48 rounded-[var(--radius-control)] px-3 py-2 text-ink-2">
            {m.zoomInFor3d}
          </p>
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
          card={items.find((c) => c.id === selectedId) ?? null}
          dict={dict}
          locale={locale}
          onClose={() => onSelect(null)}
        />
      )}
    </div>
  );
}

/** One instrument: a 40 px square; active = accent glyph with a 2 px bar. */
function ToolFace({ icon, active }: { icon: IconName; active: boolean }) {
  return (
    <span
      className={`press relative grid size-10 cursor-pointer place-items-center rounded-[var(--radius-control)] transition-colors duration-[var(--duration-quick)] hover:bg-fill ${active ? "text-accent" : "text-ink-2 hover:text-ink"}`}
    >
      <span
        aria-hidden
        className={`absolute inset-y-2.5 start-0 w-0.5 rounded-full bg-accent-fill transition-transform duration-[var(--duration-base)] ease-[var(--ease-standard)] ${active ? "scale-y-100" : "scale-y-0"}`}
      />
      <Icon name={icon} className="size-[19px]" strokeWidth={1.7} />
    </span>
  );
}

function Switch({
  checked,
  onChange,
  label,
  swatch,
  layer,
}: {
  checked: boolean;
  onChange: (on: boolean) => void;
  label: string;
  swatch?: string;
  layer?: string;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 py-1.5 text-ink">
      <span className="flex items-center gap-2.5">
        {swatch && (
          <span aria-hidden className="size-2.5 rounded-full" style={{ background: swatch }} />
        )}
        {label}
      </span>
      <input
        type="checkbox"
        data-layer={layer}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className="relative h-5 w-9 shrink-0 rounded-full bg-fill-strong transition-colors duration-[var(--duration-quick)] peer-checked:bg-accent-fill peer-focus-visible:ring-2 peer-focus-visible:ring-accent after:absolute after:start-0.5 after:top-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition-transform after:duration-[var(--duration-base)] peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4"
      />
    </label>
  );
}

/** Layers: base map, then what is drawn on it — each with its own legend swatch. */
function LayerPanel({
  dict,
  hasSatellite,
  satellite,
  setSatellite,
  buildings3d,
  setBuildings3d,
  zoom,
  future,
  setFuture,
  showAreas,
  setShowAreas,
  placeGroups,
  togglePlaces,
  placesBlocked,
}: {
  dict: Dictionary;
  hasSatellite: boolean;
  satellite: boolean;
  setSatellite: (on: boolean) => void;
  buildings3d: boolean;
  setBuildings3d: (on: boolean) => void;
  zoom: number;
  future: boolean;
  setFuture: (on: boolean) => void;
  showAreas: boolean;
  setShowAreas: (on: boolean) => void;
  placeGroups: Set<string>;
  togglePlaces: (key: string) => void;
  placesBlocked: boolean;
}) {
  const m = dict.map;
  return (
    <div className="surface-focus pop-in absolute end-[calc(100%+0.75rem)] top-0 flex w-[17.5rem] origin-top-right flex-col rounded-[var(--radius-card)] p-4 text-sm rtl:origin-top-left">
      <p className="meta mb-2 font-medium">{m.base}</p>
      {hasSatellite && (
        <div className="seg mb-2 w-full" role="group">
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
      <Switch checked={buildings3d} onChange={setBuildings3d} label={m.buildings3d} />
      {buildings3d && zoom < 13 && <p className="caption -mt-0.5 mb-1">{m.zoomInFor3d}</p>}
      <p className="meta mt-3 mb-1 border-t border-hairline pt-3 font-medium">{m.overlays}</p>
      <Switch
        checked={future}
        onChange={setFuture}
        label={dict.future.layer}
        swatch="var(--gold-fill)"
        layer="future"
      />
      <Switch
        checked={showAreas}
        onChange={setShowAreas}
        label={m.areas}
        swatch="var(--spatial-fill)"
      />
      <fieldset className="mt-3 flex flex-col gap-2 border-t border-hairline pt-3">
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
        {placesBlocked && <p className="caption">{m.zoomInForPlaces}</p>}
      </fieldset>
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
      className="pointer-events-none absolute inset-x-2 bottom-2 z-[var(--z-float)] flex justify-center md:start-[calc(var(--rail)+1.5rem)] md:end-20 md:bottom-5"
    >
      <div className="surface-focus sheet-in pointer-events-auto flex w-full max-w-md flex-col gap-2.5 rounded-[var(--radius-card)] p-4 text-sm">
        <div className="flex items-start justify-between gap-3">
          <p className="title text-ink">{name}</p>
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
        <p className="caption">
          {dict.intel.source}: {sources.join(" · ")} ·{" "}
          {props.latest_source_date ? String(props.latest_source_date) : f.undated}
        </p>
        <Link
          href={`/future#${encodeURIComponent(String(props.slug))}`}
          className="link w-fit font-medium"
        >
          {f.evidence}
        </Link>
      </div>
    </div>
  );
}

/**
 * The selected listing, previewed over the open part of the map. Wide screens:
 * a photo-led card (the picture, then price, place and facts). Phones: a
 * compact row above the bottom edge, so the selection and its surroundings
 * stay visible. Rises in with the camera's glide; replays per listing.
 */
function SelectionSheet({
  props,
  card,
  dict,
  locale,
  onClose,
}: {
  props: Record<string, unknown>;
  card: PropertyCard | null;
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
  const area = formatArea((props.area_m2 as string | null) ?? null, locale);
  const where = card
    ? [placeName(card.district ?? null, locale), placeName(card.city, locale)]
        .filter(Boolean)
        .join("، ")
    : null;
  const facts: { icon: IconName; text: string }[] = [];
  if (card?.bedrooms != null) facts.push({ icon: "bed", text: String(card.bedrooms) });
  if (card?.bathrooms != null) facts.push({ icon: "bath", text: String(card.bathrooms) });
  if (area) facts.push({ icon: "area", text: area });
  const demo = props.is_demo === true;
  const router = useRouter();

  // Escape closes the preview (the map keeps its place).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-label={title}
      data-testid="map-selection"
      className="pointer-events-none absolute inset-x-2 bottom-2 z-[var(--z-float)] flex justify-center md:start-[calc(var(--rail)+1rem)] md:end-4 md:bottom-4 lg:start-[calc(var(--rail)+1.5rem)] lg:end-auto lg:bottom-6 lg:justify-start"
    >
      {/* Keyed by listing: choosing another property replays the arrival. */}
      <article
        key={id}
        className="surface-focus sheet-in pointer-events-auto relative flex w-full max-w-[34rem] gap-3.5 overflow-hidden rounded-[var(--radius-card)] p-2.5 lg:w-[22.5rem] lg:flex-col lg:gap-0 lg:p-0"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label={dict.map.close}
          className="icon-btn absolute end-2 top-2 z-10 size-9 lg:bg-canvas/70 lg:backdrop-blur-md"
        >
          <Icon name="close" className="size-4" />
        </button>
        <div
          style={{ viewTransitionName: "property-photo" }}
          className="relative aspect-[4/3] w-28 shrink-0 overflow-hidden rounded-[var(--radius-control)] bg-fill sm:w-36 lg:aspect-[16/10] lg:w-full lg:rounded-none"
        >
          {cover ? (
            <SafeImage
              src={cover}
              alt=""
              fallbackLabel="—"
              className="photo size-full object-cover"
            />
          ) : (
            <span className="grid size-full place-items-center text-ink-3">
              <Icon name="home" className="size-6 opacity-70" />
            </span>
          )}
          {demo && (
            <span className="absolute start-0 bottom-0 flex items-center gap-1.5 rounded-se-[var(--radius-tag)] bg-gold-500 px-2 py-0.5 text-[11px] font-semibold text-[#1d1405]">
              {dict.listing.demo}
              {cover && (
                <span className="hidden font-medium opacity-80 lg:inline">
                  {dict.listing.representativePhoto}
                </span>
              )}
            </span>
          )}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1 py-1 pe-9 lg:gap-1.5 lg:p-5 lg:pe-5">
          <p className="kpi text-xl text-ink lg:text-[1.625rem]">{price}</p>
          <p className="line-clamp-2 text-sm leading-snug text-ink-2 lg:text-[15px] lg:text-ink">
            {title}
          </p>
          {where && (
            <p className="meta flex min-w-0 items-center gap-1.5">
              <Icon name="pin" className="size-4 shrink-0 text-spatial" strokeWidth={1.7} />
              <span className="truncate">{where}</span>
            </p>
          )}
          {facts.length > 0 && (
            <ul className="hidden flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2 tabular lg:mt-1 lg:flex">
              {facts.map((f) => (
                <li key={f.icon} className="flex items-center gap-1.5">
                  <Icon name={f.icon} className="size-4 text-ink-3" strokeWidth={1.7} />
                  {f.text}
                </li>
              ))}
            </ul>
          )}
          {props.approximate === true && (
            <span className="mt-0.5">
              <TrustBadge kind="estimate">{dict.map.approximate}</TrustBadge>
            </span>
          )}
          <Link
            href={`/properties/${encodeURIComponent(id)}`}
            onClick={(event) => {
              // The preview's photo becomes the detail page's hero (where the
              // browser supports it and motion is welcome); otherwise a
              // normal navigation. New tab / copy link stay untouched.
              if (!isPlainClick(event) || !canTransition()) return;
              event.preventDefault();
              navigateWithTransition(router.push, `/properties/${encodeURIComponent(id)}`, id);
            }}
            className="btn btn-primary btn-sm mt-auto w-fit lg:mt-3 lg:h-11 lg:w-full"
          >
            {dict.map.openListing}
            <Icon name="arrow" className="size-4" />
          </Link>
        </div>
      </article>
    </div>
  );
}
