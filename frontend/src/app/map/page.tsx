import type { Metadata } from "next";

import { Alert } from "@/components/ui/Alert";
import { MapSearch } from "@/features/map/MapSearch";
import { runSearch } from "@/features/search/data";
import { SearchFilters } from "@/features/search/SearchFilters";
import { errorMessage, getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { type Bbox } from "@/lib/map/geo";
import { resolveMapConfig } from "@/lib/map/provider";
import { type RawParams, first, toApiQuery } from "@/lib/search";
import type { Place, ReferenceItem } from "@/types/property";
import type { Feature, FeatureCollection } from "geojson";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.map.title };
}

async function boundariesFor(params: RawParams): Promise<FeatureCollection | null> {
  const city = first(params.city_id);
  const district = first(params.district_id);
  try {
    if (district) {
      const feature = await serverApiFetch<Feature>(
        `/api/v1/locations/districts/${encodeURIComponent(district)}/geojson`,
      );
      return {
        type: "FeatureCollection",
        features: feature.properties?.has_boundary ? [feature] : [],
      };
    }
    if (city) {
      return await serverApiFetch<FeatureCollection>(
        `/api/v1/locations/boundaries?level=districts&parent_id=${encodeURIComponent(city)}`,
      );
    }
  } catch {
    // Boundaries are optional decoration; the map works without them.
  }
  return null;
}

/** Initial viewport: explicit bbox → selected place centroid → configured default. */
function initialBbox(
  defaultBbox: Bbox,
  governorates: Place[],
  cities: Place[],
  params: RawParams,
): Bbox {
  const city = cities.find((c) => c.id === first(params.city_id));
  if (city?.centroid) {
    const { lon, lat } = city.centroid;
    return [lon - 0.08, lat - 0.06, lon + 0.08, lat + 0.06];
  }
  const gov = governorates.find((g) => g.id === first(params.governorate_id));
  if (gov?.centroid) {
    const { lon, lat } = gov.centroid;
    return [lon - 0.25, lat - 0.2, lon + 0.25, lat + 0.2];
  }
  return defaultBbox;
}

export default async function MapPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  const params = await searchParams;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const config = resolveMapConfig(process.env);
  const governorateId = first(params.governorate_id);
  const [result, types, governorates, cities, boundaries] = await Promise.all([
    runSearch(`${toApiQuery({ ...params, page: undefined })}&page_size=50`.replace(/^&/, "")),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    serverApiFetch<Place[]>("/api/v1/locations/governorates"),
    governorateId
      ? serverApiFetch<Place[]>(
          `/api/v1/locations/cities?governorate_id=${encodeURIComponent(governorateId)}`,
        ).catch(() => [] as Place[])
      : Promise.resolve([] as Place[]),
    boundariesFor(params),
  ]);

  const filters = (
    <SearchFilters
      dict={dict}
      locale={locale}
      params={params}
      types={types}
      governorates={governorates}
      basePath="/map"
    />
  );

  // Map-first stage. Phones: between the top bar and the tab bar. From md up the
  // stage runs under the floating header, which hovers over the map;
  // --map-top tells floating panels where the free space starts.
  return (
    <div className="relative h-[calc(100dvh-var(--header-h)-var(--tabbar-h))] min-h-[520px] [--map-top:0.5rem] md:-mt-[var(--header-h)] md:h-dvh md:[--map-top:var(--header-h)]">
      {"error" in result ? (
        <div className="mx-auto max-w-xl px-4 pt-[calc(var(--map-top)+1.5rem)]">
          <h1 className="display-md mb-4 text-ink">{dict.map.title}</h1>
          <Alert tone="error">{errorMessage(dict, result.error)}</Alert>
        </div>
      ) : (
        <MapSearch
          key={`${first(params.governorate_id) ?? ""}:${first(params.city_id) ?? ""}`}
          config={config}
          dict={dict}
          locale={locale}
          params={params}
          items={result.items}
          total={result.total}
          boundaries={boundaries}
          initialBbox={initialBbox(config.defaultBbox, governorates, cities, params)}
          filters={filters}
        />
      )}
    </div>
  );
}
