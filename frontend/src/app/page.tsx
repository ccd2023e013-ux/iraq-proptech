import Link from "next/link";

import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { Icon } from "@/components/ui/Icon";
import { SafeImage } from "@/components/ui/SafeImage";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { IntelligentSearch } from "@/features/home/IntelligentSearch";
import { NearYou } from "@/features/home/NearYou";
import { RiverMap } from "@/features/home/RiverMap";
import { PropertyCard, priceLabel } from "@/features/properties/PropertyCard";
import { favoriteIds, runSearch } from "@/features/search/data";
import { getDictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { stagger } from "@/lib/motion";
import type { MarketCity, MarketSummary } from "@/types/market";
import type { PropertyCard as Card, ReferenceItem } from "@/types/property";

// Rendered per request: listings, counts and locale come from the live API/cookies.
export const dynamic = "force-dynamic";

const NEXT_MODULES = [
  { key: "future", icon: "M3 20h18M5 20V9l7-5 7 5v11M9 20v-6h6v6", href: "/future" },
  { key: "vision", icon: "M3 17l6-6 4 4 8-8M14 7h7v7", href: "/vision" },
  { key: "studio", icon: "M4 6h11v12H4zM15 10l5-3v10l-5-3", href: "/studio" },
  { key: "invest", icon: "M12 3v18M7 8h7a3 3 0 0 1 0 6H8a3 3 0 0 0 0 6h9", href: null },
] as const;

function LeadListing({
  card,
  locale,
  demoLabel,
}: {
  card: Card;
  locale: Locale;
  demoLabel: string;
}) {
  const dict = getDictionary(locale);
  const title = locale === "en" && card.title_en ? card.title_en : card.title_ar;
  return (
    <Link
      href={`/properties/${card.id}`}
      className="group relative block overflow-hidden rounded-[var(--radius-media)] bg-fill shadow-[inset_0_0_0_1px_var(--hairline),var(--shadow-soft)]"
    >
      <div className="aspect-[4/3] w-full lg:aspect-[16/11]">
        {card.cover_url ? (
          <SafeImage
            src={card.cover_url.replace("?variant=thumb", "")}
            alt=""
            fallbackLabel={dict.listing.noImage}
            className="size-full object-cover transition duration-[var(--duration-slow)] ease-[var(--ease-out-soft)] group-hover:scale-[1.02]"
          />
        ) : (
          <div className="skeleton size-full" />
        )}
      </div>
      <div className="surface-float absolute inset-x-3 bottom-3 rounded-[var(--radius-card)] p-4 transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-soft)] group-hover:-translate-y-0.5">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-ink-2">
            {dict.listing.purposes[card.purpose]}
          </span>
          {card.is_demo && <TrustBadge kind="demo">{demoLabel}</TrustBadge>}
        </div>
        <p className="mt-1 line-clamp-1 font-display text-lg font-semibold text-ink">{title}</p>
        <p className="font-display text-xl font-semibold text-accent tabular">
          {priceLabel(card, dict, locale)}
        </p>
      </div>
    </Link>
  );
}

export default async function HomePage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const h = dict.homeV2;
  const [cities, types, me, favorites] = await Promise.all([
    serverApiFetch<MarketCity[]>("/api/v1/market/cities").catch(() => [] as MarketCity[]),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    getCurrentUser(),
    favoriteIds(),
  ]);
  const basra = cities.find((c) => c.slug === "basra");
  const [basraListings, basraMarket] = await Promise.all([
    basra
      ? runSearch(`city_id=${basra.city_id}&sort=newest&page_size=5`)
      : Promise.resolve({ error: "none" }),
    basra
      ? serverApiFetch<MarketSummary>(`/api/v1/market/summary?city_id=${basra.city_id}`).catch(
          () => null,
        )
      : Promise.resolve(null),
  ]);
  const name = (p: { name_ar: string; name_en: string }) =>
    locale === "ar" ? p.name_ar : p.name_en;
  const typeNames = new Map(types.map((t) => [t.code, name(t)]));
  const counts = Object.fromEntries(cities.map((c) => [c.slug, c.listings]));
  const featured = "items" in basraListings ? basraListings.items : [];
  const [lead, ...rest] = featured;
  const anyDemo = cities.some((c) => c.includes_demo);

  const segment = (type: string, purpose: string) =>
    basraMarket?.segments.find(
      (s) => s.property_type_code === type && s.purpose === purpose && s.currency === "IQD",
    );
  const houses = segment("HOUSE", "SALE");
  const flats = segment("APARTMENT", "RENT");
  const n = (v: number) => v.toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US");

  return (
    <div className="flex flex-col">
      {/* Hero stage: Iraq drawn by its rivers is the ground; the search floats
          above it. On wide screens the stage runs under the floating header. */}
      <section className="relative isolate overflow-hidden md:-mt-[var(--header-h)]">
        <div aria-hidden className="stage-grid absolute inset-0 -z-10" />
        <div
          aria-hidden
          className="absolute -z-10 size-[44rem] rounded-full bg-[radial-gradient(closest-side,var(--spatial-tint),transparent)] opacity-70 max-lg:hidden lg:end-[-10rem] lg:top-24"
        />
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 pt-10 pb-14 sm:px-6 md:pt-[calc(var(--header-h)+3.5rem)] lg:min-h-[min(88vh,56rem)] lg:grid-cols-[1.02fr_0.98fr] lg:gap-14 lg:pb-20">
          <div className="relative z-10 flex flex-col gap-6">
            <p
              lang="en"
              dir="ltr"
              className="reveal flex w-fit items-center gap-2 self-start rounded-full bg-fill px-3 py-1 text-xs font-medium text-ink-2"
            >
              <span aria-hidden className="size-1.5 rounded-full bg-spatial-fill" />
              Property · Spatial · Market Intelligence
            </p>
            <h1 className="reveal display-xl max-w-[14ch] text-ink" style={stagger(1)}>
              {h.heroTitle}
            </h1>
            <p className="reveal max-w-xl text-lg text-ink-2" style={stagger(2)}>
              {h.heroSubtitle}
            </p>
            <div className="reveal" style={stagger(3)}>
              <IntelligentSearch
                dict={dict}
                cities={cities.map((c) => ({ value: c.city_id, label: name(c) }))}
                types={types
                  .filter((t) => ["RESIDENTIAL", "LAND", "COMMERCIAL"].includes(t.category))
                  .map((t) => ({ value: t.code, label: name(t) }))}
              />
            </div>
            {anyDemo && (
              <p className="reveal flex items-center gap-2 text-xs text-ink-3" style={stagger(4)}>
                <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                {dict.footer.demoNotice}
              </p>
            )}
          </div>
          <div className="fade-in relative mx-auto w-full max-w-lg lg:max-w-none">
            <RiverMap locale={locale} counts={counts} caption={h.mapCaption} />
            <Link
              href="/map"
              className="press surface-float absolute end-2 bottom-8 inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm font-medium text-ink"
            >
              <Icon name="map" className="size-4 text-spatial" />
              {h.basraMap}
            </Link>
          </div>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-24 px-4 sm:px-6">
        {/* Basra first */}
        {lead && basra && (
          <section aria-labelledby="basra-heading" className="grid gap-8 lg:grid-cols-[0.8fr_2fr]">
            <div className="flex flex-col gap-3 lg:pt-4">
              <h2 id="basra-heading" className="display-md text-ink">
                {h.basraTitle}
              </h2>
              <p className="text-ink-2">{h.basraBody}</p>
              <p className="text-sm text-ink-3 tabular">
                {n(basra.listings)} {h.listings}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Link
                  href={`/properties?city_id=${basra.city_id}`}
                  className="inline-flex h-10 items-center rounded-full bg-accent-fill px-5 text-sm font-medium text-on-accent hover:bg-accent-fill-hover"
                >
                  {h.basraAll}
                </Link>
                <Link
                  href="/map"
                  className="inline-flex h-10 items-center rounded-full px-5 text-sm font-medium text-ink ring-1 ring-inset ring-hairline-strong hover:bg-fill"
                >
                  {h.basraMap}
                </Link>
              </div>
            </div>
            <div className="grid gap-6 md:grid-cols-[1.4fr_1fr]">
              <LeadListing card={lead} locale={locale} demoLabel={dict.listing.demo} />
              <div className="grid grid-cols-2 gap-4">
                {rest.slice(0, 4).map((card) => (
                  <PropertyCard
                    key={card.id}
                    card={card}
                    dict={dict}
                    locale={locale}
                    typeName={typeNames.get(card.property_type_code)}
                    favorite={favorites.has(card.id)}
                    signedIn={!!me}
                    compact
                  />
                ))}
              </div>
            </div>
          </section>
        )}

        {/* Market reading */}
        {basraMarket && basraMarket.listings > 0 && (
          <section aria-labelledby="market-heading" className="grid gap-8 lg:grid-cols-[0.8fr_2fr]">
            <div className="flex flex-col gap-3">
              <h2 id="market-heading" className="display-md text-ink">
                {h.marketTitle}
              </h2>
              <p className="text-ink-2">{h.marketBody}</p>
              <div className="flex gap-2">
                <TrustBadge kind="observed">{dict.market.kinds.OBSERVED}</TrustBadge>
                {basraMarket.includes_demo && (
                  <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                )}
              </div>
              <Link
                href={basra ? `/market?city_id=${basra.city_id}` : "/market"}
                className="self-start text-sm font-medium text-accent underline-offset-4 hover:underline"
              >
                {dict.market.homeLink}
              </Link>
            </div>
            <dl className="surface-1 grid gap-px overflow-hidden rounded-[var(--radius-card)] bg-hairline sm:grid-cols-2">
              {[
                {
                  label: `${h.housesForSale} · ${h.medianPerM2}`,
                  value: houses?.median_price_per_m2,
                  count: houses?.listings,
                },
                {
                  label: `${h.apartmentsForRent} · ${h.medianRent}`,
                  value: flats?.median_price,
                  count: flats?.listings,
                },
              ].map((stat) => (
                <div key={stat.label} className="flex flex-col gap-3 bg-surface p-6 sm:p-8">
                  <dt className="text-sm text-ink-2">{stat.label}</dt>
                  <dd className="kpi text-4xl text-ink sm:text-5xl">
                    {stat.value && Number.isFinite(Number(stat.value)) ? (
                      <AnimatedNumber value={Number(stat.value)} as="price-iqd" locale={locale} />
                    ) : (
                      <span className="text-2xl text-ink-3">{h.noData}</span>
                    )}
                  </dd>
                  {stat.count ? (
                    <dd className="text-xs text-ink-3">
                      {h.basedOn.replace("{n}", n(stat.count))}
                    </dd>
                  ) : null}
                </div>
              ))}
            </dl>
          </section>
        )}

        {/* Explore by city */}
        {cities.length > 0 && (
          <section aria-labelledby="explore-heading" className="flex flex-col gap-6">
            <h2 id="explore-heading" className="display-md text-ink">
              {h.exploreTitle}
            </h2>
            <ul className="grid divide-y divide-hairline border-y border-hairline sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4">
              {cities.slice(0, 8).map((c) => (
                <li key={c.city_id} className="sm:border-b sm:border-hairline">
                  <Link
                    href={`/properties?city_id=${c.city_id}`}
                    className="group flex items-baseline justify-between gap-3 px-1 py-5 transition hover:bg-fill/60 sm:px-4"
                  >
                    <span className="font-display text-xl font-semibold text-ink group-hover:text-accent">
                      {name(c)}
                    </span>
                    <span className="text-sm text-ink-3 tabular">
                      {n(c.listings)} {h.listings}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <NearYou dict={dict} locale={locale} />

        {/* In development — honest previews, no fake data. */}
        <section aria-labelledby="next-heading" className="grid gap-8 lg:grid-cols-[0.8fr_2fr]">
          <div className="flex flex-col gap-3">
            <h2 id="next-heading" className="display-md text-ink">
              {h.nextTitle}
            </h2>
            <p className="text-ink-2">{h.nextBody}</p>
          </div>
          <ul className="grid gap-x-10 gap-y-8 sm:grid-cols-2">
            {NEXT_MODULES.map((m) => (
              <li key={m.key} className="flex gap-4">
                <span className="surface-1 grid size-11 shrink-0 place-items-center rounded-2xl text-accent">
                  <svg
                    aria-hidden
                    viewBox="0 0 24 24"
                    className="size-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d={m.icon} />
                  </svg>
                </span>
                <div className="flex flex-col gap-1">
                  <p className="font-display text-lg font-semibold text-ink">
                    {h[`${m.key}Title` as const]}
                  </p>
                  <p className="text-sm text-ink-2">{h[`${m.key}Body` as const]}</p>
                  {m.href ? (
                    <Link
                      href={m.href}
                      className="mt-1 w-fit text-sm font-medium text-accent underline-offset-4 hover:underline"
                    >
                      {h.explore}
                    </Link>
                  ) : (
                    <span className="mt-1 w-fit rounded-full bg-fill px-2 py-0.5 text-[11px] font-medium text-ink-3">
                      {h.inDevelopment}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* List a property */}
        <section className="flex flex-col items-start justify-between gap-4 rounded-[var(--radius-media)] bg-accent-tint px-6 py-10 sm:flex-row sm:items-center sm:px-10">
          <div>
            <h2 className="font-display text-2xl font-semibold text-ink">{h.listTitle}</h2>
            <p className="mt-1 text-ink-2">{h.listBody}</p>
          </div>
          <Link
            href={me ? "/dashboard/properties/new" : "/register"}
            className="inline-flex h-11 shrink-0 items-center rounded-full bg-accent-fill px-6 font-medium text-on-accent shadow-soft hover:bg-accent-fill-hover"
          >
            {h.listButton}
          </Link>
        </section>
      </div>
    </div>
  );
}
