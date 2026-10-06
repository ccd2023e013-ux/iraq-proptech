import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { PropertyCard } from "@/features/properties/PropertyCard";
import { favoriteIds, runSearch } from "@/features/search/data";
import { SaveSearchButton } from "@/features/search/SaveSearchButton";
import { SearchFilters, SortSelect } from "@/features/search/SearchFilters";
import { getDictionary, errorMessage } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { stagger } from "@/lib/motion";
import { type RawParams, toApiQuery, withParam } from "@/lib/search";
import type { Place, ReferenceItem } from "@/types/property";

export const dynamic = "force-dynamic";

export default async function PropertiesPage({
  searchParams,
}: {
  searchParams: Promise<RawParams>;
}) {
  const params = await searchParams;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const [result, types, governorates, me, favorites] = await Promise.all([
    runSearch(toApiQuery(params)),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    serverApiFetch<Place[]>("/api/v1/locations/governorates"),
    getCurrentUser(),
    favoriteIds(),
  ]);
  const typeNames = new Map(types.map((t) => [t.code, locale === "ar" ? t.name_ar : t.name_en]));
  const s = dict.search;

  return (
    <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[300px_1fr]">
      <aside className="lg:sticky lg:top-[calc(var(--header-h)+1rem)] lg:self-start">
        <details className="surface-1 rounded-[var(--radius-card)] p-4 lg:open:block" open>
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-ink lg:hidden [&::-webkit-details-marker]:hidden">
            <Icon name="filter" className="size-4 text-ink-2" />
            {s.filters}
          </summary>
          <div className="mt-3 lg:mt-0">
            <SearchFilters
              dict={dict}
              locale={locale}
              params={params}
              types={types}
              governorates={governorates}
            />
          </div>
        </details>
      </aside>

      <section aria-labelledby="results-heading" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 id="results-heading" className="flex items-baseline gap-3">
            <span className="display-md text-ink">{s.title}</span>
            {"total" in result && (
              <span className="text-sm font-normal text-ink-3 tabular">
                {result.total} {s.results}
              </span>
            )}
          </h1>
          <div className="flex flex-wrap items-center gap-3">
            {"filters" in result && (
              <SaveSearchButton
                dict={dict}
                filters={result.filters}
                signedIn={!!me}
                nextPath={`/properties?${toApiQuery(params)}`}
              />
            )}
            <Link href="/search/smart" className="chip">
              <Icon name="insight" className="size-4" />
              {dict.ai.smartSearch}
            </Link>
            <Link href={`/map?${toApiQuery(params)}`} className="chip">
              <Icon name="map" className="size-4 text-spatial" />
              {dict.nav.map}
            </Link>
            <SortSelect dict={dict} params={params} />
          </div>
        </div>

        {"error" in result ? (
          <Alert tone="error">{errorMessage(dict, result.error)}</Alert>
        ) : result.items.length === 0 ? (
          <EmptyState title={s.noResults} glyph="search" />
        ) : (
          <>
            <ul className="grid gap-x-5 gap-y-9 sm:grid-cols-2 xl:grid-cols-3">
              {result.items.map((card, i) => (
                <li key={card.id} className="reveal" style={stagger(i)}>
                  <PropertyCard
                    card={card}
                    dict={dict}
                    locale={locale}
                    typeName={typeNames.get(card.property_type_code)}
                    favorite={favorites.has(card.id)}
                    signedIn={!!me}
                  />
                </li>
              ))}
            </ul>
            <Pagination
              page={result.page}
              pages={Math.ceil(result.total / result.page_size)}
              params={params}
              labels={{ previous: s.previous, next: s.next, page: s.page }}
            />
          </>
        )}
      </section>
    </div>
  );
}

function Pagination({
  page,
  pages,
  params,
  labels,
}: {
  page: number;
  pages: number;
  params: RawParams;
  labels: { previous: string; next: string; page: string };
}) {
  if (pages <= 1) return null;
  const link =
    "press surface-1 inline-flex h-10 items-center gap-1.5 rounded-full px-4 text-sm font-medium text-ink";
  return (
    <nav aria-label="pagination" className="flex items-center justify-center gap-3">
      {page > 1 && (
        <Link className={link} href={`/properties?${withParam(params, "page", String(page - 1))}`}>
          {labels.previous}
        </Link>
      )}
      <span className="text-sm text-ink-3 tabular">
        {labels.page} {page} / {pages}
      </span>
      {page < pages && (
        <Link className={link} href={`/properties?${withParam(params, "page", String(page + 1))}`}>
          {labels.next}
        </Link>
      )}
    </nav>
  );
}
