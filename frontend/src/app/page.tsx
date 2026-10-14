import Link from "next/link";
import type { ReactNode } from "react";

import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { Icon, type IconName } from "@/components/ui/Icon";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { IntelligentSearch } from "@/features/home/IntelligentSearch";
import { NearYou } from "@/features/home/NearYou";
import { RiverMap } from "@/features/home/RiverMap";
import { MapPreview } from "@/features/map/MapPreview";
import { PropertyCard } from "@/features/properties/PropertyCard";
import { favoriteIds, runSearch } from "@/features/search/data";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { tagLabel } from "@/lib/map/bubbles";
import { resolveMapConfig } from "@/lib/map/provider";
import { stagger } from "@/lib/motion";
import type { MarketCity, MarketSummary } from "@/types/market";
import type { ReferenceItem } from "@/types/property";

// Rendered per request: listings, counts and locale come from the live API/cookies.
export const dynamic = "force-dynamic";

const NEXT_MODULES: {
  key: "future" | "vision" | "studio" | "invest";
  icon: IconName;
  href: string | null;
}[] = [
  { key: "future", icon: "future", href: "/future" },
  { key: "vision", icon: "insight", href: "/vision" },
  { key: "studio", icon: "grid", href: "/studio" },
  { key: "invest", icon: "market", href: null },
];

/** A section's opening: the title and its sentence at the start, actions at the end. */
function SectionHead({
  id,
  title,
  body,
  actions,
}: {
  id: string;
  title: string;
  body?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 md:mb-10 md:flex-row md:items-end md:justify-between">
      <div className="flex max-w-2xl flex-col gap-2">
        <h2 id={id} className="display-md text-ink">
          {title}
        </h2>
        {body && <p className="text-lg text-ink-2">{body}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export default async function HomePage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const h = dict.homeV2;
  const mapConfig = resolveMapConfig(process.env);
  const [cities, types, me, favorites] = await Promise.all([
    serverApiFetch<MarketCity[]>("/api/v1/market/cities").catch(() => [] as MarketCity[]),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    getCurrentUser(),
    favoriteIds(),
  ]);
  const basra = cities.find((c) => c.slug === "basra");
  const [basraListings, basraMarket] = await Promise.all([
    basra
      ? runSearch(`city_id=${basra.city_id}&sort=newest&page_size=50`)
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
  const all = "items" in basraListings ? basraListings.items : [];
  // The hero map shows every located listing with its asking price.
  const points = all.flatMap((c) =>
    c.display_location
      ? [
          {
            lon: c.display_location.lon,
            lat: c.display_location.lat,
            precision: "exact" as const,
            label: tagLabel(c.price_amount, c.currency, c.price_on_request, c.rent_period, locale),
          },
        ]
      : [],
  );
  // Photographed listings lead; one large, four smaller.
  const photographed = all.filter((c) => c.cover_url);
  const lead = photographed[0] ?? all[0];
  const rest = (photographed.length > 1 ? photographed : all).filter((c) => c !== lead).slice(0, 4);
  const anyDemo = cities.some((c) => c.includes_demo);

  const segment = (type: string, purpose: string) =>
    basraMarket?.segments.find(
      (s) => s.property_type_code === type && s.purpose === purpose && s.currency === "IQD",
    );
  const houses = segment("HOUSE", "SALE");
  const flats = segment("APARTMENT", "RENT");
  const n = (v: number) => v.toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US");
  const counts = Object.fromEntries(cities.map((c) => [c.slug, c.listings]));
  const card = (c: (typeof all)[number], compact = false) => (
    <PropertyCard
      card={c}
      dict={dict}
      locale={locale}
      typeName={typeNames.get(c.property_type_code)}
      favorite={favorites.has(c.id)}
      signedIn={!!me}
      compact={compact}
    />
  );

  return (
    <div className="flex flex-col">
      {/* Hero: Basra itself — the live map of its listings with their asking
          prices — under the headline and the search. On wide screens the map
          fills the stage behind; on phones it follows the search. */}
      <section aria-labelledby="hero-title" className="relative isolate overflow-hidden">
        <div className="page relative z-10 flex flex-col justify-center gap-7 pt-10 pb-8 md:min-h-[min(82vh,840px)] md:py-20">
          <div className="flex max-w-[35rem] flex-col gap-7">
            <h1 id="hero-title" className="reveal display-xl text-ink">
              {h.heroTitle}
            </h1>
            <p className="reveal lede" style={stagger(1)}>
              {h.heroSubtitle}
            </p>
            <div className="reveal" style={stagger(2)}>
              <IntelligentSearch
                dict={dict}
                cities={cities.map((c) => ({ value: c.city_id, label: name(c) }))}
                types={types
                  .filter((t) => ["RESIDENTIAL", "LAND", "COMMERCIAL"].includes(t.category))
                  .map((t) => ({ value: t.code, label: name(t) }))}
              />
            </div>
            {anyDemo && (
              <p className="reveal caption flex items-start gap-2" style={stagger(3)}>
                <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                {dict.footer.demoNotice}
              </p>
            )}
          </div>
        </div>
        {points.length > 0 && (
          <div className="relative mx-4 h-[24rem] overflow-hidden rounded-[var(--radius-card)] md:absolute md:inset-0 md:-z-0 md:mx-0 md:h-auto md:rounded-none">
            <MapPreview
              config={mapConfig}
              tags
              intro
              startInset={0.46}
              className="h-full rounded-none shadow-none"
              label={h.heroMapCaption.replace("{n}", n(points.length))}
              points={points}
            />
            {/* Legibility: the canvas washes in under the text column only. */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-y-0 start-0 hidden w-[min(58%,820px)] bg-gradient-to-r from-canvas via-canvas/90 to-transparent md:block rtl:bg-gradient-to-l"
            />
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 bottom-0 hidden h-28 bg-gradient-to-t from-canvas to-transparent md:block"
            />
          </div>
        )}
        {points.length > 0 && (
          <div className="page relative z-10 flex items-center justify-between gap-4 py-4 md:absolute md:inset-x-0 md:bottom-6 md:py-0 md:ps-[max(var(--gutter),50%)]">
            <span className="meta flex items-center gap-2 text-ink-2">
              <span aria-hidden className="inline-block size-2 rounded-full bg-spatial-fill" />
              {h.heroMapCaption.replace("{n}", n(basra?.listings ?? points.length))}
            </span>
            <Link href="/map" className="btn btn-secondary btn-sm shrink-0">
              <Icon name="map" className="size-4 text-spatial" />
              {h.openMap}
            </Link>
          </div>
        )}
      </section>

      <div className="page flex flex-col gap-24 pt-16 md:gap-32 md:pt-24">
        {/* Basra first: photographs lead — one large, four smaller. */}
        {lead && basra && (
          <section aria-labelledby="basra-heading">
            <SectionHead
              id="basra-heading"
              title={h.basraTitle}
              body={h.basraBody}
              actions={
                <>
                  <Link href={`/properties?city_id=${basra.city_id}`} className="btn btn-primary">
                    {h.basraAll}
                  </Link>
                  <Link href="/map" className="btn btn-secondary">
                    {h.basraMap}
                  </Link>
                </>
              }
            />
            <div className="grid grid-cols-1 gap-x-6 gap-y-10 lg:grid-cols-12">
              <div className="lg:col-span-7">{card(lead)}</div>
              <ul className="grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-2 lg:col-span-5">
                {rest.map((c) => (
                  <li key={c.id}>{card(c, true)}</li>
                ))}
              </ul>
            </div>
          </section>
        )}

        {/* Market reading: a band of measured figures, with their provenance. */}
        {basraMarket && basraMarket.listings > 0 && (
          <section
            aria-labelledby="market-heading"
            className="grid gap-10 rounded-[var(--radius-card)] bg-surface p-8 shadow-[var(--edge),0_0_0_1px_var(--hairline)] md:p-12 lg:grid-cols-12"
          >
            <div className="flex flex-col gap-4 lg:col-span-5">
              <h2 id="market-heading" className="display-md text-ink">
                {h.marketTitle}
              </h2>
              <p className="text-lg text-ink-2">{h.marketBody}</p>
              <div className="flex flex-wrap gap-2">
                <TrustBadge kind="observed">{dict.market.kinds.OBSERVED}</TrustBadge>
                {basraMarket.includes_demo && (
                  <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                )}
              </div>
              <Link
                href={basra ? `/market?city_id=${basra.city_id}` : "/market"}
                className="link mt-2 w-fit font-medium"
              >
                {dict.market.homeLink}
              </Link>
            </div>
            <dl className="grid gap-10 sm:grid-cols-2 lg:col-span-7">
              {[
                {
                  label: h.housesForSale,
                  sub: h.medianPerM2,
                  value: houses?.median_price_per_m2,
                  count: houses?.listings,
                },
                {
                  label: h.apartmentsForRent,
                  sub: h.medianRent,
                  value: flats?.median_price,
                  count: flats?.listings,
                },
              ].map((stat) => (
                <div key={stat.label} className="flex flex-col gap-3">
                  <dt className="flex flex-col">
                    <span className="font-medium text-ink">{stat.label}</span>
                    <span className="meta">{stat.sub}</span>
                  </dt>
                  <dd className="kpi text-5xl text-ink lg:text-6xl">
                    {stat.value && Number.isFinite(Number(stat.value)) ? (
                      <AnimatedNumber value={Number(stat.value)} as="price-iqd" locale={locale} />
                    ) : (
                      <span className="text-2xl font-normal tracking-normal text-ink-3">
                        {h.noData}
                      </span>
                    )}
                  </dd>
                  {stat.count ? (
                    <dd className="meta">{h.basedOn.replace("{n}", n(stat.count))}</dd>
                  ) : null}
                </div>
              ))}
            </dl>
          </section>
        )}

        {/* The country by its rivers, and the cities we cover. */}
        {cities.length > 0 && (
          <section aria-labelledby="explore-heading" className="grid gap-10 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <h2 id="explore-heading" className="display-md mb-6 text-ink">
                {h.exploreTitle}
              </h2>
              <RiverMap locale={locale} counts={counts} caption={h.mapCaption} animate={false} />
            </div>
            <ul className="flex flex-col self-end lg:col-span-7">
              {cities.slice(0, 8).map((c) => (
                <li key={c.city_id} className="border-b border-hairline first:border-t">
                  <Link
                    href={`/properties?city_id=${c.city_id}`}
                    className="group flex items-center justify-between gap-4 py-5"
                  >
                    <span className="title text-ink transition-colors group-hover:text-accent">
                      {name(c)}
                    </span>
                    <span className="flex items-center gap-4">
                      <span className="meta tabular">
                        {n(c.listings)} {h.listings}
                      </span>
                      <Icon
                        name="chevron"
                        className="size-4 text-ink-3 transition-transform duration-[var(--duration-base)] group-hover:translate-x-0.5 group-hover:text-ink rtl:group-hover:-translate-x-0.5"
                      />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <NearYou dict={dict} locale={locale} />

        {/* In development: honest previews, no fake data. */}
        <section aria-labelledby="next-heading">
          <SectionHead id="next-heading" title={h.nextTitle} body={h.nextBody} />
          <ul className="grid gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
            {NEXT_MODULES.map((m) => (
              <li key={m.key} className="flex flex-col gap-3">
                <span
                  aria-hidden
                  className="grid size-11 place-items-center rounded-full bg-spatial-tint text-spatial"
                >
                  <Icon name={m.icon} className="size-5" />
                </span>
                <p className="title text-ink">{h[`${m.key}Title` as const]}</p>
                <p className="text-ink-2">{h[`${m.key}Body` as const]}</p>
                {m.href ? (
                  <Link href={m.href} className="link mt-1 w-fit font-medium">
                    {h.explore}
                  </Link>
                ) : (
                  <span className="mt-1 w-fit rounded-[var(--radius-tag)] bg-fill px-2.5 py-1 text-xs font-medium text-ink-3">
                    {h.inDevelopment}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>

        {/* List a property: one closing action. */}
        <section className="flex flex-col items-start justify-between gap-6 rounded-[var(--radius-card)] bg-accent-tint p-8 md:flex-row md:items-center md:p-12">
          <div className="flex flex-col gap-2">
            <h2 className="display-md text-ink">{h.listTitle}</h2>
            <p className="text-lg text-ink-2">{h.listBody}</p>
          </div>
          <Link
            href={me ? "/dashboard/properties/new" : "/register"}
            className="btn btn-primary btn-lg shrink-0"
          >
            <Icon name="plus" className="size-4" strokeWidth={2} />
            {h.listButton}
          </Link>
        </section>
      </div>
    </div>
  );
}
