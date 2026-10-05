import type { Metadata } from "next";
import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { ProviderBadge } from "@/features/ai/ProviderBadge";
import { PropertyCard } from "@/features/properties/PropertyCard";
import { favoriteIds } from "@/features/search/data";
import { errorMessage, getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { filtersToQuery, first, type RawParams } from "@/lib/search";
import type { AIEnvelope, ParseResult } from "@/types/ai";
import type { PropertyCard as Card } from "@/types/property";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.ai.smartSearch };
}

interface NLSearch {
  interpretation: AIEnvelope<ParseResult>;
  items: Card[];
  total: number;
}

export default async function SmartSearchPage({
  searchParams,
}: {
  searchParams: Promise<RawParams>;
}) {
  const q = (first((await searchParams).q) ?? "").trim();
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.ai;
  let data: NLSearch | null = null;
  let error: string | null = null;
  if (q.length >= 2) {
    try {
      data = await serverApiFetch<NLSearch>(
        `/api/v1/ai/search?q=${encodeURIComponent(q)}&page_size=24`,
      );
    } catch (err) {
      error = err instanceof ApiError ? err.code : "UNKNOWN";
    }
  }
  const [me, favorites] = await Promise.all([getCurrentUser(), favoriteIds()]);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
      <h1 className="flex items-center gap-2 text-2xl font-bold text-brand-900">
        {a.smartSearch}
        <span className="rounded bg-brand-700 px-1.5 py-0.5 text-xs font-bold text-on-accent">
          {a.badge}
        </span>
      </h1>
      <form method="get" action="/search/smart" role="search" className="flex gap-2">
        <input
          name="q"
          defaultValue={q}
          placeholder={a.smartSearchPlaceholder}
          aria-label={a.smartSearch}
          minLength={2}
          maxLength={300}
          className="h-12 min-w-0 flex-1 rounded-lg border border-sand-200 bg-surface px-4"
        />
        <button type="submit" className="rounded-lg bg-brand-700 px-5 font-medium text-on-accent">
          {dict.landing.heroCta}
        </button>
      </form>
      {error && <Alert tone="error">{errorMessage(dict, error)}</Alert>}
      {data && (
        <>
          <section aria-label={a.understood} className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold text-sand-700">{a.understood}</h2>
            <ProviderBadge
              dict={dict}
              provider={data.interpretation.provider}
              model={data.interpretation.model}
            />
            <ul className="flex flex-wrap gap-2">
              {data.interpretation.result.understood.map((u, i) => (
                <li key={i} className="rounded-full bg-brand-50 px-3 py-1 text-xs text-brand-800">
                  «{u.phrase}» → {u.field}: {u.value}
                </li>
              ))}
            </ul>
            {data.interpretation.result.ambiguities.map((amb) => (
              <Alert key={amb} tone="warning">
                {a.ambiguities[amb as keyof typeof a.ambiguities] ?? amb}
              </Alert>
            ))}
            {data.interpretation.result.unparsed && (
              <p className="text-xs text-sand-500">
                {a.unparsed}: {data.interpretation.result.unparsed}
              </p>
            )}
            <Link
              href={`/properties?${filtersToQuery(data.interpretation.result.filters)}`}
              className="text-sm font-medium text-accent"
            >
              {dict.search.filters} →
            </Link>
          </section>
          <p className="text-sm text-sand-700 tabular">
            {data.total} {dict.search.results}
          </p>
          {data.items.length === 0 ? (
            <p className="rounded-[var(--radius-card)] border border-dashed border-sand-200 py-12 text-center text-sand-500">
              {dict.search.noResults}
            </p>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.items.map((card) => (
                <li key={card.id}>
                  <PropertyCard
                    card={card}
                    dict={dict}
                    locale={locale}
                    favorite={favorites.has(card.id)}
                    signedIn={!!me}
                  />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
