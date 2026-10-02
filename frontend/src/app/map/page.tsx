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

  return (
    <div className="mx-auto grid max-w-[1600px] gap-4 px-4 py-4 sm:px-6 xl:grid-cols-[280px_1fr]">
      <aside className="xl:sticky xl:top-20 xl:self-start">
        <details className="rounded-[var(--radius-card)] border border-sand-200 bg-white p-4">
          <summary className="cursor-pointer text-sm font-semibold text-brand-900">
            {dict.search.filters}
          </summary>
          <div className="mt-3">
            <SearchFilters
              dict={dict}
              locale={locale}
              params={params}
              types={types}
              governorates={governorates}
              basePath="/map"
            />
          </div>
        </details>
      </aside>
      <section className="flex flex-col gap-3">
        <h1 className="text-xl font-bold text-brand-900">{dict.map.title}</h1>
        {"error" in result ? (
          <Alert tone="error">{errorMessage(dict, result.error)}</Alert>
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
          />
        )}
      </section>
    </div>
  );
}
