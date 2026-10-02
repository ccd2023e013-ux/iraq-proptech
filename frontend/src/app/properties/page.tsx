import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { PropertyCard } from "@/features/properties/PropertyCard";
import { favoriteIds, runSearch } from "@/features/search/data";
import { SaveSearchButton } from "@/features/search/SaveSearchButton";
import { SearchFilters, SortSelect } from "@/features/search/SearchFilters";
import { getDictionary, errorMessage } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
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
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[300px_1fr]">
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <details
          className="rounded-[var(--radius-card)] border border-sand-200 bg-white p-4 lg:open:block"
          open
        >
          <summary className="cursor-pointer text-sm font-semibold text-brand-900 lg:hidden">
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
          <h1 id="results-heading" className="text-xl font-bold text-brand-900">
            {s.title}
            {"total" in result && (
              <span className="ms-2 text-sm font-normal text-sand-500 tabular">
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
            <Link href="/search/smart" className="text-sm font-medium text-brand-700">
              {dict.ai.smartSearch}
            </Link>
            <Link
              href={`/map?${toApiQuery(params)}`}
              className="text-sm font-medium text-brand-700"
            >
              {dict.nav.map}
            </Link>
            <SortSelect dict={dict} params={params} />
          </div>
        </div>

        {"error" in result ? (
          <Alert tone="error">{errorMessage(dict, result.error)}</Alert>
        ) : result.items.length === 0 ? (
          <p className="rounded-[var(--radius-card)] border border-dashed border-sand-200 py-16 text-center text-sand-500">
            {s.noResults}
          </p>
        ) : (
          <>
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {result.items.map((card) => (
                <li key={card.id}>
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
  const link = "rounded-lg border border-sand-200 px-3 py-1.5 text-sm hover:border-brand-300";
  return (
    <nav aria-label="pagination" className="flex items-center justify-center gap-3">
      {page > 1 && (
        <Link className={link} href={`/properties?${withParam(params, "page", String(page - 1))}`}>
          {labels.previous}
        </Link>
      )}
      <span className="text-sm text-sand-500 tabular">
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
