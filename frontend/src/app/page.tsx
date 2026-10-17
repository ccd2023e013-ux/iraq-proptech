import Link from "next/link";
import type { ReactNode } from "react";

import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { Icon } from "@/components/ui/Icon";
import { IntelligentSearch } from "@/features/home/IntelligentSearch";
import { NearYou } from "@/features/home/NearYou";
import { RiverMap } from "@/features/home/RiverMap";
import { MapPreview } from "@/features/map/MapPreview";
import { ListingRow } from "@/features/properties/ListingRow";
import { PropertyCard } from "@/features/properties/PropertyCard";
import { favoriteIds, runSearch } from "@/features/search/data";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { tagLabel } from "@/lib/map/bubbles";
import { resolveMapConfig } from "@/lib/map/provider";
import { distinctCovers } from "@/lib/photos";
import type { MarketCity, MarketSummary } from "@/types/market";
import type { ReferenceItem } from "@/types/property";

// Rendered per request: listings, counts and locale come from the live API/cookies.
export const dynamic = "force-dynamic";

const NEXT_MODULES: { key: "future" | "vision" | "studio" | "invest"; href: string | null }[] = [
  { key: "future", href: "/future" },
  { key: "vision", href: "/vision" },
  { key: "studio", href: "/studio" },
  { key: "invest", href: null },
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
    <div className="mb-8 flex flex-col gap-4 border-t border-hairline-strong pt-6 md:mb-10 md:flex-row md:items-end md:justify-between">
      <div className="flex max-w-2xl flex-col gap-2">
        <h2 id={id} className="display-md text-ink">
          {title}
        </h2>
        {body && <p className="text-ink-2">{body}</p>}
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
  // The ledger beside the map: the newest listings, each photograph shown
  // once in this view (lib/photos). The editorial section below leads with
  // listings whose photograph is distinct.
  const newest = all.slice(0, 5);
  const ledgerPhotos = distinctCovers(newest);
  const photographed = all.filter((c) => c.cover_url);
  const firstOfType = photographed.filter(
    (c, i) => photographed.findIndex((o) => o.property_type_code === c.property_type_code) === i,
  );
  const lead = firstOfType[0] ?? all[0];
  const rest = (firstOfType.length > 1 ? firstOfType : all).filter((c) => c !== lead).slice(0, 4);
  const editorialPhotos = distinctCovers(
    [lead, ...rest].filter((c): c is NonNullable<typeof c> => !!c),
  );
  const anyDemo = cities.some((c) => c.includes_demo);

  const segment = (type: string, purpose: string) =>
    basraMarket?.segments.find(
      (s) => s.property_type_code === type && s.purpose === purpose && s.currency === "IQD",
    );
  const houses = segment("HOUSE", "SALE");
  const flats = segment("APARTMENT", "RENT");
  const n = (v: number) => v.toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US");
  const counts = Object.fromEntries(cities.map((c) => [c.slug, c.listings]));
  const total = "total" in basraListings ? basraListings.total : points.length;
  // Purpose split only when every listing is in hand (no guessing from a page).
  const split =
    all.length === total
      ? {
          sale: all.filter((c) => c.purpose === "SALE").length,
          rent: all.filter((c) => c.purpose === "RENT").length,
        }
      : null;
  // Where the plate is centred: the middle of the listings' extent, which is
  // where the map opens (it fits to the same points).
  const centre = points.length
    ? {
        lat: (Math.min(...points.map((p) => p.lat)) + Math.max(...points.map((p) => p.lat))) / 2,
        lon: (Math.min(...points.map((p) => p.lon)) + Math.max(...points.map((p) => p.lon))) / 2,
      }
    : null;
  const card = (c: (typeof all)[number], compact = false, feature = false) => (
    <PropertyCard
      card={c}
      dict={dict}
      locale={locale}
      typeName={typeNames.get(c.property_type_code)}
      favorite={favorites.has(c.id)}
      signedIn={!!me}
      compact={compact}
      feature={feature}
      cover={editorialPhotos.get(c.id) ?? null}
    />
  );
  const basraName = basra ? name(basra) : locale === "ar" ? "البصرة" : "Basra";

  return (
    <div className="flex flex-col">
      {/* The plate. Wide screens: the console (place, count, query, newest)
          docked at the reading start, the map filling the rest. Phones: the
          place, then the map, then the console. One map in both layouts. */}
      <section
        aria-labelledby="hero-title"
        className="grid border-b border-hairline [grid-template-areas:'place'_'map'_'console'] lg:h-[clamp(640px,calc(100svh-var(--header-h)),920px)] lg:grid-cols-[minmax(380px,30rem)_minmax(0,1fr)] lg:grid-rows-[auto_minmax(0,1fr)] lg:[grid-template-areas:'place_map'_'console_map']"
      >
        <div className="flex flex-col gap-3 bg-console px-[var(--gutter)] pt-8 pb-6 [grid-area:place] lg:border-e lg:border-hairline lg:px-8 lg:pt-10">
          <h1 id="hero-title" className="place text-ink">
            {basraName}
          </h1>
          <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <span className="font-display text-lg text-ink-2">{h.plateCountry}</span>
            {centre && (
              <span className="caption tabular" dir="ltr">
                {h.plateCentre
                  .replace("{lat}", centre.lat.toFixed(2))
                  .replace("{lon}", centre.lon.toFixed(2))}
              </span>
            )}
          </p>
          {total > 0 ? (
            <p className="mt-3 text-lg text-ink">
              <span className="kpi me-1.5 text-2xl">{n(total)}</span>
              {h.plateCount.replace("{n}", "").trim()}
              {split && (
                <span className="text-ink-2">
                  {locale === "ar" ? "، " : ": "}
                  {h.plateSplit.replace("{sale}", n(split.sale)).replace("{rent}", n(split.rent))}
                </span>
              )}
              .
            </p>
          ) : (
            <p className="mt-3 text-ink-2">{h.plateEmpty}</p>
          )}
        </div>

        {points.length > 0 && (
          <div className="relative h-[46svh] min-h-[300px] border-y border-hairline [grid-area:map] lg:h-auto lg:min-h-0 lg:border-0">
            <MapPreview
              config={mapConfig}
              tags
              intro
              className="h-full rounded-none shadow-none"
              label={h.heroMapCaption.replace("{n}", n(points.length))}
              points={points}
            />
            <Link
              href="/map"
              className="btn btn-secondary btn-sm absolute end-3 top-3 z-10 shadow-[var(--shadow-float)] lg:end-4 lg:top-4"
            >
              <Icon name="map" className="size-4 text-spatial" />
              {h.plateFullMap}
            </Link>
          </div>
        )}

        <div className="flex min-h-0 flex-col gap-8 bg-console px-[var(--gutter)] pt-6 pb-8 [grid-area:console] lg:overflow-y-auto lg:border-e lg:border-hairline lg:px-8">
          <IntelligentSearch
            dict={dict}
            defaultCity={basra?.city_id ?? ""}
            cities={cities.map((c) => ({ value: c.city_id, label: name(c) }))}
            types={types
              .filter((t) => ["RESIDENTIAL", "LAND", "COMMERCIAL"].includes(t.category))
              .map((t) => ({ value: t.code, label: name(t) }))}
          />
          {newest.length > 0 && (
            <div className="flex flex-col">
              <h2 className="label border-b border-hairline pb-2">{h.plateNewest}</h2>
              <ul className="flex flex-col divide-y divide-hairline">
                {newest.map((c) => (
                  <li key={c.id}>
                    <ListingRow
                      card={c}
                      dict={dict}
                      locale={locale}
                      photo={ledgerPhotos.get(c.id) ?? null}
                      typeName={typeNames.get(c.property_type_code)}
                    />
                  </li>
                ))}
              </ul>
            </div>
          )}
          {anyDemo && <p className="caption">{dict.footer.demoNotice}</p>}
        </div>
      </section>

      <div className="page flex flex-col gap-24 pt-20 md:gap-28 md:pt-24">
        {/* Asking prices: measurements with their provenance, not a card. */}
        {basraMarket && basraMarket.listings > 0 && (
          <section aria-labelledby="market-heading">
            <SectionHead
              id="market-heading"
              title={h.pricesTitle}
              body={h.pricesBody}
              actions={
                <Link
                  href={basra ? `/market?city_id=${basra.city_id}` : "/market"}
                  className="btn btn-secondary"
                >
                  {h.pricesMore}
                </Link>
              }
            />
            <dl className="grid gap-px overflow-hidden bg-hairline sm:grid-cols-3">
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
                <div
                  key={stat.label}
                  className="flex flex-col gap-3 bg-canvas py-6 sm:px-8 sm:first:ps-0"
                >
                  <dt className="flex flex-col">
                    <span className="font-medium text-ink">{stat.label}</span>
                    <span className="meta">{stat.sub}</span>
                  </dt>
                  <dd className="kpi text-4xl whitespace-nowrap text-ink xl:text-5xl">
                    {stat.value && Number.isFinite(Number(stat.value)) ? (
                      <AnimatedNumber value={Number(stat.value)} as="price-iqd" locale={locale} />
                    ) : (
                      <span className="font-sans text-xl font-normal tracking-normal text-ink-3">
                        {h.noData}
                      </span>
                    )}
                  </dd>
                  {stat.count ? (
                    <dd className="meta">{h.basedOn.replace("{n}", n(stat.count))}</dd>
                  ) : null}
                </div>
              ))}
              <div className="flex flex-col gap-3 bg-canvas py-6 sm:px-8">
                <dt className="flex flex-col">
                  <span className="font-medium text-ink">{dict.market.headline.listings}</span>
                  <span className="meta">{basraName}</span>
                </dt>
                <dd className="kpi text-4xl text-ink xl:text-5xl">{n(basraMarket.listings)}</dd>
                {basraMarket.includes_demo && (
                  <dd className="meta font-medium text-gold-700">{dict.listing.demo}</dd>
                )}
              </div>
            </dl>
          </section>
        )}

        {/* More of Basra: photographs lead, each shown once. */}
        {lead && basra && (
          <section aria-labelledby="basra-heading">
            <SectionHead
              id="basra-heading"
              title={h.basraTitle}
              body={h.basraBody}
              actions={
                <Link href={`/properties?city_id=${basra.city_id}`} className="btn btn-primary">
                  {h.basraAll}
                </Link>
              }
            />
            <div className="grid grid-cols-1 gap-x-8 gap-y-10 lg:grid-cols-12">
              <div className="lg:col-span-7">{card(lead, false, true)}</div>
              <ul className="grid grid-cols-1 content-start gap-x-6 gap-y-8 sm:grid-cols-2 lg:col-span-5">
                {rest.map((c) => (
                  <li key={c.id}>{card(c, true)}</li>
                ))}
              </ul>
            </div>
          </section>
        )}

        {/* The country by its rivers, and the cities on MAKAN. */}
        {cities.length > 0 && (
          <section aria-labelledby="explore-heading">
            <SectionHead id="explore-heading" title={h.citiesTitle} body={h.citiesBody} />
            <div className="grid gap-10 lg:grid-cols-12">
              <div className="lg:col-span-5">
                <RiverMap locale={locale} counts={counts} caption={h.mapCaption} animate={false} />
              </div>
              <ul className="flex flex-col self-start lg:col-span-7">
                {cities.slice(0, 8).map((c) => (
                  <li key={c.city_id} className="border-b border-hairline first:border-t">
                    <Link
                      href={`/properties?city_id=${c.city_id}`}
                      className="group flex items-center justify-between gap-4 py-4"
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
                          className="size-4 text-ink-3 transition-transform duration-[var(--duration-base)] group-hover:translate-x-0.5 group-hover:text-ink rtl:rotate-180 rtl:group-hover:-translate-x-0.5"
                        />
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}

        <NearYou dict={dict} locale={locale} />

        {/* In development: honest previews, no fake data. */}
        <section aria-labelledby="next-heading">
          <SectionHead id="next-heading" title={h.nextTitle} body={h.nextBody} />
          <ul className="grid gap-px overflow-hidden bg-hairline sm:grid-cols-2 lg:grid-cols-4">
            {NEXT_MODULES.map((m) => (
              <li key={m.key} className="flex flex-col gap-2 bg-canvas py-5 sm:pe-6">
                <p className="title text-ink">{h[`${m.key}Title` as const]}</p>
                <p className="text-[15px] text-ink-2">{h[`${m.key}Body` as const]}</p>
                {m.href ? (
                  <Link href={m.href} className="link mt-1 w-fit text-sm font-medium">
                    {h.explore}
                  </Link>
                ) : (
                  <span className="caption mt-1">{h.inDevelopment}</span>
                )}
              </li>
            ))}
          </ul>
        </section>

        {/* List a property: one closing action. */}
        <section className="flex flex-col items-start justify-between gap-6 border-t border-hairline-strong pt-8 pb-4 md:flex-row md:items-center">
          <div className="flex flex-col gap-2">
            <h2 className="display-md text-ink">{h.listTitle}</h2>
            <p className="text-ink-2">{h.listBody}</p>
          </div>
          <Link
            href={me ? "/dashboard/properties/new" : "/register"}
            className="btn btn-secondary btn-lg shrink-0"
          >
            <Icon name="plus" className="size-4" strokeWidth={2} />
            {h.listButton}
          </Link>
        </section>
      </div>
    </div>
  );
}
