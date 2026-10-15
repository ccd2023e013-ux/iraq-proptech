import type { Metadata } from "next";
import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Icon } from "@/components/ui/Icon";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { ProviderBadge } from "@/features/ai/ProviderBadge";
import { MapPreview } from "@/features/map/MapPreview";
import { PropertyCard } from "@/features/properties/PropertyCard";
import { favoriteIds } from "@/features/search/data";
import { errorMessage, getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { placeName } from "@/lib/format";
import { tagLabel } from "@/lib/map/bubbles";
import { resolveMapConfig } from "@/lib/map/provider";
import { all, filtersToQuery, type RawParams } from "@/lib/search";
import type { AIEnvelope, ParseResult } from "@/types/ai";
import type { MarketReport } from "@/types/market";
import type { PropertyCard as Card } from "@/types/property";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.ai.assistant.title };
}

interface NLSearch {
  interpretation: AIEnvelope<ParseResult>;
  items: Card[];
  total: number;
}

const MAX_TURNS = 6;
const MARKET_WORDS = /\b(market|trend|trends|median)\b|سوق|السوق|اتجاه|وسيط/i;

/**
 * MAKAN Assistant: a conversation over MAKAN's own search. Each turn is a
 * `q` in the URL (so a conversation is shareable and Back works). The reader
 * is given the newest turn first, so a later detail ("for rent") overrides an
 * earlier one ("for sale"): the parser keeps the first match per field.
 *
 * Every reply shows exactly what was understood, which provider produced it
 * (the rule-based reader is labelled as such — never as a live model), the
 * matching listings on a map, and, when asked about the market, the market
 * report's own labelled reading for that area.
 */
export default async function AssistantPage({
  searchParams,
}: {
  searchParams: Promise<RawParams>;
}) {
  const params = await searchParams;
  const turns = all(params.q)
    .map((t) => t.trim())
    .filter((t) => t.length >= 2)
    .slice(-MAX_TURNS);
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.ai;
  const s = a.assistant;
  const mapConfig = resolveMapConfig(process.env);
  const query = [...turns].reverse().join(" ");

  let data: NLSearch | null = null;
  let error: string | null = null;
  if (query) {
    try {
      data = await serverApiFetch<NLSearch>(
        `/api/v1/ai/search?q=${encodeURIComponent(query)}&page_size=12`,
      );
    } catch (err) {
      error = err instanceof ApiError ? err.code : "UNKNOWN";
    }
  }
  const filters = data?.interpretation.result.filters ?? {};
  const wantsMarket = turns.some((t) => MARKET_WORDS.test(t));
  const marketQuery = new URLSearchParams({ language: locale, include_demo: "true" });
  if (typeof filters.district_id === "string") marketQuery.set("district_id", filters.district_id);
  else if (typeof filters.city_id === "string") marketQuery.set("city_id", filters.city_id);
  const [me, favorites, market] = await Promise.all([
    getCurrentUser(),
    favoriteIds(),
    wantsMarket
      ? serverApiFetch<MarketReport>(`/api/v1/market/report?${marketQuery}`).catch(() => null)
      : Promise.resolve(null),
  ]);
  const marketReading = market?.statements.find((x) => x.kind === "AI_INTERPRETATION");

  const items = data?.items ?? [];
  const located = items.filter((c) => c.display_location);
  // Refinements the reader understands, offered only for what is still open.
  const suggestions: string[] = [];
  if (data) {
    if (filters.bedrooms_min === undefined) suggestions.push(s.suggest.beds);
    if (filters.max_price === undefined) suggestions.push(s.suggest.budget);
    if (filters.purpose === undefined) suggestions.push(s.suggest.sale, s.suggest.rent);
    if (!filters.verified_only) suggestions.push(s.suggest.verified);
    const places = Array.from(
      new Set(items.map((c) => placeName(c.district ?? null, locale)).filter(Boolean)),
    ).slice(0, 2);
    for (const place of places) suggestions.push(s.suggest.inPlace.replace("{place}", place));
    if (!wantsMarket) suggestions.push(s.suggest.market);
  }
  const withTurn = (extra: string) => {
    const q = new URLSearchParams();
    for (const t of turns) q.append("q", t);
    q.append("q", extra);
    return `/search/smart?${q}`;
  };
  const filterQuery = data ? filtersToQuery(data.interpretation.result.filters) : "";

  return (
    <div className="page flex flex-col gap-8 pt-8 pb-16 md:pt-12">
      <header className="mx-auto flex w-full max-w-3xl flex-col gap-3">
        <span className="inline-flex w-fit items-center gap-1.5 rounded-[var(--radius-tag)] bg-accent-tint px-2.5 py-1 text-[13px] font-medium text-accent">
          <Icon name="sparkle" className="size-4" />
          {a.badge}
        </span>
        <h1 className="display-lg text-ink">{s.title}</h1>
        <p className="lede">{s.lede}</p>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6" aria-live="polite">
        {/* Earlier turns: the user's words, compact. */}
        {turns.length > 1 && (
          <ol className="flex flex-col gap-2" aria-label={s.earlier}>
            {turns.slice(0, -1).map((t, i) => (
              <li key={i} className="flex justify-end">
                <p className="max-w-[80%] rounded-[var(--radius-card)] rounded-ee-md bg-fill px-4 py-2.5 text-[15px] text-ink-2">
                  {t}
                </p>
              </li>
            ))}
          </ol>
        )}
        {turns.length > 0 && (
          <div className="flex justify-end">
            <p className="max-w-[80%] rounded-[var(--radius-card)] rounded-ee-md bg-ink px-4 py-2.5 text-[15px] text-canvas">
              {turns[turns.length - 1]}
            </p>
          </div>
        )}

        {error && <Alert tone="error">{errorMessage(dict, error)}</Alert>}

        {data && (
          <article
            className="flex flex-col gap-5 rounded-[var(--radius-card)] bg-surface p-5 shadow-[inset_0_0_0_1px_var(--hairline)] md:p-7"
            data-testid="assistant-reply"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="flex items-center gap-2 font-medium text-ink">
                <span className="grid size-7 place-items-center rounded-full bg-accent-tint text-accent">
                  <Icon name="sparkle" className="size-4" />
                </span>
                {s.makan}
              </p>
              <ProviderBadge
                dict={dict}
                provider={data.interpretation.provider}
                model={data.interpretation.model}
              />
            </div>

            <div className="flex flex-col gap-2">
              <p className="meta">{a.understood}</p>
              <ul className="flex flex-wrap gap-2">
                {data.interpretation.result.understood.map((u, i) => (
                  <li
                    key={i}
                    className="inline-flex items-center overflow-hidden rounded-[var(--radius-control)] text-[13px] shadow-[inset_0_0_0_1px_var(--hairline-strong)]"
                  >
                    <span className="bg-fill px-2.5 py-1 text-ink-3">«{u.phrase}»</span>
                    <span className="px-2.5 py-1 font-medium text-ink">{u.value}</span>
                  </li>
                ))}
              </ul>
              {data.interpretation.result.ambiguities.map((amb) => (
                <Alert key={amb} tone="warning">
                  {a.ambiguities[amb as keyof typeof a.ambiguities] ?? amb}
                </Alert>
              ))}
              {data.interpretation.result.unparsed && (
                <p className="caption">
                  {a.unparsed}: {data.interpretation.result.unparsed}
                </p>
              )}
            </div>

            <p className="title text-ink">
              {data.total > 0 ? s.found.replace("{n}", String(data.total)) : s.none}
            </p>

            {located.length > 0 && (
              <MapPreview
                config={mapConfig}
                tags
                className="h-64 sm:h-80"
                label={s.found.replace("{n}", String(data.total))}
                points={located.map((c) => ({
                  lon: c.display_location!.lon,
                  lat: c.display_location!.lat,
                  precision: "exact" as const,
                  label: tagLabel(
                    c.price_amount,
                    c.currency,
                    c.price_on_request,
                    c.rent_period,
                    locale,
                  ),
                }))}
              />
            )}

            {data.total > 0 && (
              <div className="flex flex-wrap gap-2">
                <Link href={`/map?${filterQuery}`} className="btn btn-primary btn-sm">
                  <Icon name="map" className="size-4" />
                  {s.openMap}
                </Link>
                <Link href={`/properties?${filterQuery}`} className="btn btn-secondary btn-sm">
                  <Icon name="list" className="size-4" />
                  {s.openList}
                </Link>
              </div>
            )}

            {wantsMarket && market && (
              <section className="flex flex-col gap-2 border-t border-hairline pt-5">
                <p className="meta">{s.marketNote}</p>
                {marketReading?.text ? (
                  <>
                    <p className="flex flex-wrap gap-2">
                      <TrustBadge kind="ai">{dict.market.kinds.AI_INTERPRETATION}</TrustBadge>
                      {marketReading.demo && (
                        <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                      )}
                    </p>
                    <p className="text-[15px] leading-relaxed text-ink">{marketReading.text}</p>
                  </>
                ) : (
                  <p className="text-ink-2">{dict.market.empty}</p>
                )}
                <Link
                  href={`/market?${marketQuery.has("district_id") ? `district_id=${marketQuery.get("district_id")}` : marketQuery.has("city_id") ? `city_id=${marketQuery.get("city_id")}` : ""}`}
                  className="link w-fit text-sm font-medium"
                >
                  {s.openMarket}
                </Link>
              </section>
            )}

            {suggestions.length > 0 && (
              <div className="flex flex-col gap-2 border-t border-hairline pt-5">
                <p className="meta">{s.refine}</p>
                <ul className="flex flex-wrap gap-2">
                  {suggestions.map((x) => (
                    <li key={x}>
                      <Link href={withTurn(x)} className="chip">
                        <Icon name="plus" className="size-3.5" />
                        {x}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>
        )}

        {/* Composer: a follow-up adds a turn; earlier turns ride along. */}
        <form
          method="get"
          action="/search/smart"
          role="search"
          className="surface-float flex items-center gap-2 rounded-[var(--radius-card)] p-2 ps-4 focus-within:shadow-[var(--edge),0_0_0_2px_var(--accent),var(--shadow-float)]"
        >
          {turns.map((t, i) => (
            <input key={i} type="hidden" name="q" value={t} />
          ))}
          <Icon name="sparkle" className="size-5 shrink-0 text-accent" />
          <input
            name="q"
            placeholder={turns.length ? s.followUp : a.smartSearchPlaceholder}
            aria-label={s.title}
            minLength={2}
            maxLength={300}
            required
            autoFocus={turns.length === 0}
            className="h-12 min-w-0 flex-1 bg-transparent text-[16px] text-ink outline-none placeholder:text-ink-3"
          />
          <button type="submit" className="btn btn-primary shrink-0" aria-label={s.send}>
            <Icon name="send" className="size-4" />
            <span className="max-sm:sr-only">{s.send}</span>
          </button>
        </form>
        <div className="flex flex-wrap items-center justify-between gap-3">
          {turns.length === 0 ? (
            <ul className="flex flex-wrap gap-2">
              {a.smartExamples.map((example) => (
                <li key={example}>
                  <Link href={`/search/smart?q=${encodeURIComponent(example)}`} className="chip">
                    {example}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <Link href="/search/smart" className="btn btn-quiet btn-sm">
              <Icon name="refresh" className="size-4" />
              {s.newChat}
            </Link>
          )}
        </div>
        <p className="caption">{s.honesty}</p>
      </div>

      {items.length > 0 && (
        <ul className="grid gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((card) => (
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
    </div>
  );
}
