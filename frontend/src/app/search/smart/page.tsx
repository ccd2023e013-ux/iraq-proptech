import type { Metadata } from "next";
import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Icon } from "@/components/ui/Icon";
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
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:px-6">
      <header className="flex flex-col items-center gap-4 pt-6 text-center">
        <span className="inline-flex items-center gap-1.5 rounded-[var(--radius-tag)] bg-spatial-tint px-3 py-1 text-xs font-medium text-spatial">
          <Icon name="insight" className="size-3.5" />
          {a.badge}
        </span>
        <h1 className="display-lg text-ink">{a.smartSearch}</h1>
        <p className="max-w-xl text-ink-2">{a.smartSearchIntro}</p>
      </header>
      <form
        method="get"
        action="/search/smart"
        role="search"
        className="surface-float mx-auto flex w-full max-w-3xl items-center gap-2 rounded-[var(--radius-control)] p-1.5 ps-4 focus-within:shadow-[var(--edge),0_0_0_2px_var(--accent),var(--shadow-float)]"
      >
        <Icon name="search" className="size-5 shrink-0 text-ink-3" />
        <input
          name="q"
          defaultValue={q}
          placeholder={a.smartSearchPlaceholder}
          aria-label={a.smartSearch}
          minLength={2}
          maxLength={300}
          className="h-11 min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-ink-3"
        />
        <button
          type="submit"
          className="press inline-flex h-11 shrink-0 items-center rounded-[var(--radius-control)] bg-accent-fill px-5 font-medium text-on-accent hover:bg-accent-fill-hover"
        >
          {dict.landing.heroCta}
        </button>
      </form>
      {!q && (
        <ul className="mx-auto flex max-w-3xl flex-wrap justify-center gap-2">
          {a.smartExamples.map((example) => (
            <li key={example}>
              <Link
                href={`/search/smart?q=${encodeURIComponent(example)}`}
                className="press inline-flex h-9 items-center gap-1.5 rounded-[var(--radius-control)] px-3.5 text-sm text-ink-2 ring-1 ring-inset ring-hairline-strong hover:bg-fill hover:text-ink"
              >
                <span className="text-ink-3">{a.tryExample}:</span> {example}
              </Link>
            </li>
          ))}
        </ul>
      )}
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
                <li
                  key={i}
                  className="inline-flex items-center overflow-hidden rounded-[var(--radius-control)] text-xs ring-1 ring-inset ring-hairline-strong"
                >
                  <span className="bg-fill px-2.5 py-1 text-ink-2">«{u.phrase}»</span>
                  <span className="px-2.5 py-1 text-ink">
                    {u.field}: <strong className="font-semibold">{u.value}</strong>
                  </span>
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
              className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-accent"
            >
              {dict.search.filters}
              <Icon name="arrow" className="size-4" />
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
