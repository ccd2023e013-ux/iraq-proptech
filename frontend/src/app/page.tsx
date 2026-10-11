import Link from "next/link";
import type { ReactNode } from "react";

import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { Icon, type IconName } from "@/components/ui/Icon";
import { SafeImage } from "@/components/ui/SafeImage";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { IntelligentSearch } from "@/features/home/IntelligentSearch";
import { NearYou } from "@/features/home/NearYou";
import { MapPreview } from "@/features/map/MapPreview";
import { priceLabel } from "@/features/properties/PropertyCard";
import { runSearch } from "@/features/search/data";
import { getDictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { formatArea, placeName } from "@/lib/format";
import { resolveMapConfig } from "@/lib/map/provider";
import { stagger } from "@/lib/motion";
import type { MarketCity, MarketSummary } from "@/types/market";
import type { PropertyCard as Card, ReferenceItem } from "@/types/property";

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

/** One editorial section: a title column at the start, content at the end. */
function Section({
  id,
  title,
  aside,
  children,
}: {
  id: string;
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className="rule-top grid grid-cols-[minmax(0,1fr)] gap-8 pt-10 md:grid-cols-12 md:gap-6 md:pt-12"
    >
      <div className="flex min-w-0 flex-col gap-3 md:col-span-4 lg:col-span-3">
        <h2 id={id} className="display-md text-ink">
          {title}
        </h2>
        {aside}
      </div>
      <div className="min-w-0 md:col-span-8 lg:col-span-9">{children}</div>
    </section>
  );
}

function where(card: Card, locale: Locale): string {
  return [placeName(card.neighborhood ?? card.district, locale), placeName(card.city, locale)]
    .filter(Boolean)
    .join("، ");
}

export default async function HomePage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const h = dict.homeV2;
  const mapConfig = resolveMapConfig(process.env);
  const [cities, types, me] = await Promise.all([
    serverApiFetch<MarketCity[]>("/api/v1/market/cities").catch(() => [] as MarketCity[]),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    getCurrentUser(),
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
  const points = all.flatMap((c) =>
    c.display_location
      ? [{ lon: c.display_location.lon, lat: c.display_location.lat, precision: "exact" as const }]
      : [],
  );
  // The lead needs a photograph; the ledger lists the next four.
  const lead = all.find((c) => c.cover_url) ?? all[0];
  const ledger = all.filter((c) => c !== lead).slice(0, 4);
  const anyDemo = cities.some((c) => c.includes_demo);

  const segment = (type: string, purpose: string) =>
    basraMarket?.segments.find(
      (s) => s.property_type_code === type && s.purpose === purpose && s.currency === "IQD",
    );
  const houses = segment("HOUSE", "SALE");
  const flats = segment("APARTMENT", "RENT");
  const n = (v: number) => v.toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US");
  const title = (c: Card) => (locale === "en" && c.title_en ? c.title_en : c.title_ar);

  return (
    <div className="flex flex-col">
      {/* Hero: the headline and search at the start; a live, quiet map of Basra's
          listings at the end, bleeding to the page edge. */}
      <section className="relative isolate overflow-hidden">
        <div className="mx-auto grid max-w-[1320px] grid-cols-[minmax(0,1fr)] gap-10 px-4 pt-10 pb-12 sm:px-6 md:grid-cols-12 md:gap-6 md:pt-16 lg:min-h-[min(80vh,46rem)] lg:px-8 lg:pb-20">
          <div className="relative z-10 flex min-w-0 flex-col justify-center gap-7 md:col-span-6">
            <h1 className="reveal display-xl text-ink">{h.heroTitle}</h1>
            <p className="reveal max-w-[34rem] text-[17px] text-ink-2" style={stagger(1)}>
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
          {points.length > 0 && (
            <figure className="fade-in relative min-w-0 md:col-span-6 md:-me-6 lg:-me-8 xl:-me-[calc((100vw-1320px)/2+2rem)]">
              <MapPreview
                config={mapConfig}
                dense
                className="h-[22rem] rounded-none sm:h-[28rem] md:h-full md:min-h-[30rem] md:rounded-s-[var(--radius-card)] md:rounded-e-none"
                label={h.heroMapCaption.replace("{n}", n(points.length))}
                points={points}
              />
              <figcaption className="mt-3 flex items-center justify-between gap-4 md:absolute md:inset-x-4 md:bottom-4 md:mt-0">
                <span className="caption md:rounded-[var(--radius-control)] md:bg-raised/80 md:px-3 md:py-2 md:text-ink-2 md:shadow-[var(--shadow-float)] md:backdrop-blur-xl">
                  <span className="me-1.5 inline-block size-2 rounded-full bg-accent-fill align-middle" />
                  {h.heroMapCaption.replace("{n}", n(basra?.listings ?? points.length))}
                </span>
                <Link
                  href="/map"
                  className="press inline-flex h-9 shrink-0 items-center gap-2 rounded-[var(--radius-control)] px-3 text-sm font-medium text-ink shadow-[inset_0_0_0_1px_var(--hairline-strong)] hover:bg-fill md:bg-raised/80 md:shadow-[var(--shadow-float)] md:backdrop-blur-xl"
                >
                  <Icon name="map" className="size-4 text-spatial" />
                  {h.openMap}
                </Link>
              </figcaption>
            </figure>
          )}
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1320px] flex-col gap-24 px-4 sm:px-6 lg:px-8">
        {/* Basra first: one photographed lead and a ruled ledger of the next four. */}
        {lead && basra && (
          <Section
            id="basra-heading"
            title={h.basraTitle}
            aside={
              <>
                <p className="text-ink-2">{h.basraBody}</p>
                <p className="kpi mt-2 text-4xl text-ink">
                  {n(basra.listings)}
                  <span className="ms-2 text-sm font-normal tracking-normal text-ink-3">
                    {h.listings}
                  </span>
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link
                    href={`/properties?city_id=${basra.city_id}`}
                    className="press inline-flex h-10 items-center rounded-[var(--radius-control)] bg-accent-fill px-4 text-sm font-medium text-on-accent hover:bg-accent-fill-hover"
                  >
                    {h.basraAll}
                  </Link>
                  <Link
                    href="/map"
                    className="press inline-flex h-10 items-center rounded-[var(--radius-control)] px-4 text-sm font-medium text-ink shadow-[inset_0_0_0_1px_var(--hairline-strong)] hover:bg-fill"
                  >
                    {h.basraMap}
                  </Link>
                </div>
              </>
            }
          >
            <div className="grid grid-cols-1 gap-8 lg:grid-cols-9 lg:gap-6">
              <Link
                href={`/properties/${lead.id}`}
                className="group flex min-w-0 flex-col gap-4 lg:col-span-5"
              >
                <div className="relative aspect-[4/3] overflow-hidden rounded-[var(--radius-card)] bg-fill">
                  {lead.cover_url ? (
                    <SafeImage
                      src={lead.cover_url.replace("?variant=thumb", "")}
                      alt=""
                      fallbackLabel={dict.listing.noImage}
                      className="size-full object-cover transition-transform duration-[var(--duration-slow)] ease-[var(--ease-standard)] group-hover:scale-[1.015]"
                    />
                  ) : (
                    <div className="skeleton size-full" />
                  )}
                  {lead.is_demo && (
                    <span className="absolute start-3 bottom-3">
                      <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <p className="kpi text-3xl text-ink">{priceLabel(lead, dict, locale)}</p>
                  <p className="text-ink group-hover:underline group-hover:decoration-hairline-strong group-hover:underline-offset-4">
                    {title(lead)}
                  </p>
                  <p className="meta">
                    {dict.listing.purposes[lead.purpose]} · {where(lead, locale)}
                  </p>
                </div>
              </Link>
              <ol className="flex min-w-0 flex-col border-t border-hairline lg:col-span-4">
                {ledger.map((card) => {
                  const area = formatArea(card.area_m2, locale);
                  return (
                    <li key={card.id} className="border-b border-hairline">
                      <Link
                        href={`/properties/${card.id}`}
                        className="group flex items-center gap-4 py-4 transition-colors"
                      >
                        <span className="relative size-[4.5rem] shrink-0 overflow-hidden rounded-[var(--radius-control)] bg-fill">
                          {card.cover_url ? (
                            <SafeImage
                              src={card.cover_url}
                              alt=""
                              fallbackLabel="—"
                              className="size-full object-cover"
                            />
                          ) : (
                            <span className="grid size-full place-items-center text-ink-3">
                              <Icon name="home" className="size-5 opacity-70" />
                            </span>
                          )}
                        </span>
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="kpi text-lg text-ink">
                            {priceLabel(card, dict, locale)}
                          </span>
                          <span className="truncate text-sm text-ink-2 group-hover:text-ink">
                            {title(card)}
                          </span>
                          <span className="caption truncate">
                            {[typeNames.get(card.property_type_code), area, where(card, locale)]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </span>
                        {card.is_demo && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
                      </Link>
                    </li>
                  );
                })}
              </ol>
            </div>
          </Section>
        )}

        {/* Market reading: two measured figures, ruled, with their provenance. */}
        {basraMarket && basraMarket.listings > 0 && (
          <Section
            id="market-heading"
            title={h.marketTitle}
            aside={
              <>
                <p className="text-ink-2">{h.marketBody}</p>
                <div className="flex gap-2">
                  <TrustBadge kind="observed">{dict.market.kinds.OBSERVED}</TrustBadge>
                  {basraMarket.includes_demo && (
                    <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                  )}
                </div>
                <Link
                  href={basra ? `/market?city_id=${basra.city_id}` : "/market"}
                  className="link mt-1 w-fit text-sm font-medium"
                >
                  {dict.market.homeLink}
                </Link>
              </>
            }
          >
            <dl className="grid grid-cols-1 border-t border-hairline sm:grid-cols-2 sm:divide-x sm:divide-hairline rtl:sm:divide-x-reverse">
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
                  className="flex flex-col gap-2 border-b border-hairline py-6 sm:px-6 sm:first:ps-0"
                >
                  <dt className="text-sm text-ink">
                    {stat.label}
                    <span className="block text-ink-3">{stat.sub}</span>
                  </dt>
                  <dd className="kpi mt-2 text-4xl text-ink sm:text-5xl">
                    {stat.value && Number.isFinite(Number(stat.value)) ? (
                      <AnimatedNumber value={Number(stat.value)} as="price-iqd" locale={locale} />
                    ) : (
                      <span className="text-2xl font-normal tracking-normal text-ink-3">
                        {h.noData}
                      </span>
                    )}
                  </dd>
                  {stat.count ? (
                    <dd className="caption">{h.basedOn.replace("{n}", n(stat.count))}</dd>
                  ) : null}
                </div>
              ))}
            </dl>
          </Section>
        )}

        {/* City index: a ruled table of places, not tiles. */}
        {cities.length > 0 && (
          <Section id="explore-heading" title={h.exploreTitle}>
            <ul className="grid grid-cols-1 border-t border-hairline sm:grid-cols-2 sm:gap-x-6">
              {cities.slice(0, 8).map((c) => (
                <li key={c.city_id} className="border-b border-hairline">
                  <Link
                    href={`/properties?city_id=${c.city_id}`}
                    className="group flex items-baseline justify-between gap-3 py-4"
                  >
                    <span className="font-display text-xl font-semibold text-ink transition-colors group-hover:text-accent">
                      {name(c)}
                    </span>
                    <span className="flex items-center gap-3 text-sm text-ink-3 tabular">
                      {n(c.listings)} {h.listings}
                      <Icon
                        name="arrow"
                        className="size-4 opacity-0 transition-[opacity,translate] duration-[var(--duration-base)] group-hover:translate-x-0.5 group-hover:opacity-100 rtl:group-hover:-translate-x-0.5"
                      />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <NearYou dict={dict} locale={locale} />

        {/* In development: honest previews, no fake data. */}
        <Section
          id="next-heading"
          title={h.nextTitle}
          aside={<p className="text-ink-2">{h.nextBody}</p>}
        >
          <ul className="grid grid-cols-1 border-t border-hairline sm:grid-cols-2 sm:gap-x-6">
            {NEXT_MODULES.map((m) => (
              <li key={m.key} className="flex gap-4 border-b border-hairline py-6">
                <Icon name={m.icon} className="mt-1 size-5 shrink-0 text-spatial" />
                <div className="flex flex-col gap-1">
                  <p className="title text-ink">{h[`${m.key}Title` as const]}</p>
                  <p className="text-sm text-ink-2">{h[`${m.key}Body` as const]}</p>
                  {m.href ? (
                    <Link href={m.href} className="link mt-1 w-fit text-sm font-medium">
                      {h.explore}
                    </Link>
                  ) : (
                    <span className="mt-1 w-fit rounded-[var(--radius-tag)] bg-fill px-2 py-0.5 text-[11px] font-medium text-ink-3">
                      {h.inDevelopment}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Section>

        {/* List a property: a ruled band with one primary action. */}
        <section className="rule-top flex flex-col items-start justify-between gap-6 pt-10 sm:flex-row sm:items-end">
          <div>
            <h2 className="display-md text-ink">{h.listTitle}</h2>
            <p className="mt-2 text-ink-2">{h.listBody}</p>
          </div>
          <Link
            href={me ? "/dashboard/properties/new" : "/register"}
            className="press inline-flex h-12 shrink-0 items-center gap-2 rounded-[var(--radius-control)] bg-accent-fill px-5 font-medium text-on-accent hover:bg-accent-fill-hover"
          >
            <Icon name="plus" className="size-4" strokeWidth={2} />
            {h.listButton}
          </Link>
        </section>
      </div>
    </div>
  );
}
