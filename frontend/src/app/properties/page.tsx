import { headers } from "next/headers";
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
  const phone = /Mobi|iPhone|Android/i.test((await headers()).get("user-agent") ?? "");
  const typeNames = new Map(types.map((t) => [t.code, locale === "ar" ? t.name_ar : t.name_en]));
  const s = dict.search;

  return (
    <div className="mx-auto grid max-w-[1320px] grid-cols-[minmax(0,1fr)] gap-6 px-4 py-8 sm:px-6 md:py-12 lg:grid-cols-12 lg:gap-8 lg:px-8">
      {/* Filters are a ruled column on the page, not a box. Phones start with
          them folded so results lead; desktops keep them open. */}
      <aside className="min-w-0 lg:sticky lg:top-[calc(var(--header-h)+1.5rem)] lg:col-span-3 lg:max-h-[calc(100dvh-var(--header-h)-3rem)] lg:self-start lg:overflow-y-auto lg:border-e lg:border-hairline lg:pe-6 quiet-scroll">
        <details className="border-y border-hairline py-3 lg:border-0 lg:py-0" open={!phone}>
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-medium text-ink lg:hidden [&::-webkit-details-marker]:hidden">
            <span className="flex items-center gap-2">
              <Icon name="filter" className="size-4 text-ink-2" />
              {s.filters}
            </span>
            <Icon name="chevron-down" className="size-4 text-ink-3" />
          </summary>
          <div className="mt-4 lg:mt-0">
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

      <section
        aria-labelledby="results-heading"
        className="flex min-w-0 flex-col gap-8 lg:col-span-9"
      >
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-hairline pb-5">
          <h1 id="results-heading" className="flex flex-col gap-1">
            <span className="display-lg text-ink">{s.title}</span>
            {"total" in result && (
              <span className="meta tabular">
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
            <ul className="grid grid-cols-1 gap-x-6 gap-y-10 sm:grid-cols-2 xl:grid-cols-3">
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
    "press inline-flex h-10 items-center gap-1.5 rounded-[var(--radius-control)] px-4 text-sm font-medium text-ink shadow-[inset_0_0_0_1px_var(--hairline-strong)] hover:bg-fill";
  return (
    <nav
      aria-label="pagination"
      className="flex items-center justify-between gap-3 border-t border-hairline pt-6"
    >
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
