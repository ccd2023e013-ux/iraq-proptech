import Link from "next/link";

import { PropertyCard } from "@/features/properties/PropertyCard";
import { favoriteIds, runSearch } from "@/features/search/data";
import { HeroSearch } from "@/features/search/HeroSearch";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import type { Place, ReferenceItem } from "@/types/property";

// Rendered per request: latest listings and locale come from the live API/cookies.
export const dynamic = "force-dynamic";

/** Governorates highlighted on the landing page (Basra first). Purely presentational. */
const FEATURED_GOVERNORATES = ["BSR", "BGD", "EBL", "NIN", "NJF", "KRB"];

export default async function HomePage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const l = dict.landing;
  const [latest, types, governorates, me, favorites] = await Promise.all([
    runSearch("sort=newest&page_size=6"),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    serverApiFetch<Place[]>("/api/v1/locations/governorates"),
    getCurrentUser(),
    favoriteIds(),
  ]);
  const name = (p: { name_ar: string; name_en: string }) =>
    locale === "ar" ? p.name_ar : p.name_en;
  const typeNames = new Map(types.map((t) => [t.code, name(t)]));
  const featured = FEATURED_GOVERNORATES.map((code) =>
    governorates.find((g) => g.code === code),
  ).filter((g): g is Place => !!g);
  const residential = types.filter((t) => t.category === "RESIDENTIAL").slice(0, 8);
  const shownTypes = residential.length ? residential : types.slice(0, 8);

  return (
    <div className="flex flex-col">
      <section className="bg-gradient-to-b from-brand-900 to-brand-800 text-white">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-6 px-4 py-14 text-center sm:px-6 lg:py-20">
          <h1 className="text-3xl leading-tight font-bold sm:text-5xl">{l.heroTitle}</h1>
          <p className="max-w-2xl text-brand-100 sm:text-lg">{l.heroSubtitle}</p>
          <HeroSearch dict={dict} />
          <Link href="/search/smart" className="text-sm text-brand-100 underline">
            {dict.ai.smartSearch} — {dict.ai.smartSearchPlaceholder}
          </Link>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-12 px-4 py-12 sm:px-6">
        <section aria-labelledby="types-heading" className="flex flex-col gap-4">
          <h2 id="types-heading" className="text-xl font-bold text-brand-900">
            {l.categories}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {shownTypes.map((t) => (
              <li key={t.code}>
                <Link
                  href={`/properties?property_types=${encodeURIComponent(t.code)}`}
                  className="block rounded-full border border-sand-200 bg-white px-4 py-2 text-sm hover:border-brand-300 hover:text-brand-700"
                >
                  {name(t)}
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="locations-heading" className="flex flex-col gap-4">
          <h2 id="locations-heading" className="text-xl font-bold text-brand-900">
            {l.locations}
          </h2>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {featured.map((g) => (
              <li key={g.id}>
                <Link
                  href={`/properties?governorate_id=${g.id}`}
                  className="flex h-20 items-center justify-center rounded-[var(--radius-card)] border border-sand-200 bg-white font-semibold text-brand-800 hover:border-brand-300"
                >
                  {name(g)}
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="latest-heading" className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 id="latest-heading" className="text-xl font-bold text-brand-900">
              {l.latest}
            </h2>
            <Link href="/properties" className="text-sm font-medium text-brand-700">
              {l.viewAll}
            </Link>
          </div>
          {"items" in latest && latest.items.length > 0 ? (
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {latest.items.map((card) => (
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
          ) : (
            <p className="rounded-[var(--radius-card)] border border-dashed border-sand-200 py-12 text-center text-sand-500">
              {dict.search.noResults}
            </p>
          )}
        </section>

        <section
          aria-labelledby="trust-heading"
          className="grid gap-4 rounded-[var(--radius-card)] bg-white p-6 sm:grid-cols-3"
        >
          <h2 id="trust-heading" className="text-xl font-bold text-brand-900 sm:col-span-3">
            {l.trustTitle}
          </h2>
          {[l.trust1, l.trust2, l.trust3].map((text) => (
            <p key={text} className="border-s-4 border-gold-300 ps-3 text-sm text-sand-700">
              {text}
            </p>
          ))}
        </section>

        <section className="flex flex-col items-center gap-4 rounded-[var(--radius-card)] bg-gold-100 px-6 py-10 text-center">
          <h2 className="text-2xl font-bold text-brand-900">{l.listCta}</h2>
          <Link
            href={me ? "/dashboard/properties/new" : "/register"}
            className="rounded-lg bg-brand-700 px-6 py-3 font-medium text-white hover:bg-brand-800"
          >
            {l.listCtaButton}
          </Link>
        </section>

        <p className="text-center text-xs text-sand-500">
          <Link href="/status" className="underline">
            {l.statusLink}
          </Link>
        </p>
      </div>
    </div>
  );
}
