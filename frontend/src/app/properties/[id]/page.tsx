import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { Alert } from "@/components/ui/Alert";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { Insights } from "@/features/ai/Insights";
import { IntelligencePanel } from "@/features/ai/IntelligencePanel";
import { PropertySummary } from "@/features/ai/PropertySummary";
import { ReportButton } from "@/features/admin/ReportButton";
import { ViewBeacon } from "@/features/analytics/ViewBeacon";
import { InquiryForm } from "@/features/crm/InquiryForm";
import { FavoriteButton } from "@/features/properties/FavoriteButton";
import { Gallery, ShareButton } from "@/features/properties/Gallery";
import { Nearby } from "@/features/properties/Nearby";
import { favoriteIds } from "@/features/search/data";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { formatArea, formatDate, formatPrice, placeName } from "@/lib/format";
import type { Property, ReferenceItem } from "@/types/property";

export const dynamic = "force-dynamic";

interface Verification {
  id: string;
  kind: keyof ReturnType<typeof getDictionary>["property"]["checks"];
  result: "PASSED" | "FAILED";
  created_at: string;
}

interface Conversion {
  converted: string | null;
  to: "IQD" | "USD";
  rate: { source: string; effective_at: string } | null;
}

interface PricePoint {
  price_amount: string | null;
  currency: "IQD" | "USD";
  price_on_request: boolean;
  changed_at: string;
}

async function load(id: string): Promise<Property> {
  try {
    return await serverApiFetch<Property>(`/api/v1/properties/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof ApiError && [404, 422].includes(error.status)) notFound();
    throw error;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const locale = await getRequestLocale();
  try {
    const p = await serverApiFetch<Property>(`/api/v1/properties/${encodeURIComponent(id)}`);
    const title = locale === "en" && p.title_en ? p.title_en : p.title_ar;
    return { title, robots: p.is_demo ? { index: false } : undefined };
  } catch {
    return {};
  }
}

export default async function PropertyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const p = dict.property;
  const property = await load(id);
  const [verifications, history, types, amenities, me, favorites] = await Promise.all([
    serverApiFetch<Verification[]>(`/api/v1/properties/${property.id}/verifications`),
    serverApiFetch<PricePoint[]>(`/api/v1/properties/${property.id}/price-history`),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/amenities"),
    getCurrentUser(),
    favoriteIds(),
  ]);
  // Indicative equivalent in the other currency — only when an operator has configured a rate.
  const conversion =
    !property.price_on_request && property.price_amount
      ? await serverApiFetch<Conversion>(
          `/api/v1/exchange-rates/convert?amount=${encodeURIComponent(property.price_amount)}&from=${property.currency}&to=${property.currency === "USD" ? "IQD" : "USD"}`,
        ).catch(() => null)
      : null;
  const label = (items: ReferenceItem[], code: string) => {
    const item = items.find((i) => i.code === code);
    return item ? (locale === "ar" ? item.name_ar : item.name_en) : code;
  };
  const title = locale === "en" && property.title_en ? property.title_en : property.title_ar;
  const description =
    locale === "en" && property.description_en ? property.description_en : property.description_ar;
  const price = property.price_on_request
    ? dict.listing.priceOnRequest
    : `${formatPrice(property.price_amount, property.currency, locale)}${property.rent_period ? ` ${p.perPeriod[property.rent_period]}` : ""}`;
  const where = [
    placeName(property.neighborhood, locale),
    placeName(property.district, locale),
    placeName(property.city, locale),
    placeName(property.governorate, locale),
  ]
    .filter(Boolean)
    .join("، ");

  // Only facts the lister actually provided are shown (nothing is inferred).
  const facts: [string, string][] = [
    [p.type, label(types, property.property_type_code)],
    [p.purpose, dict.listing.purposes[property.purpose]],
    [dict.listing.area, formatArea(property.area_m2, locale) ?? ""],
    [dict.listing.landArea, formatArea(property.land_area_m2, locale) ?? ""],
    [dict.listing.bedrooms, property.bedrooms?.toString() ?? ""],
    [dict.listing.bathrooms, property.bathrooms?.toString() ?? ""],
    [p.floors, property.floors?.toString() ?? ""],
    [p.floorNumber, property.floor_number?.toString() ?? ""],
    [p.yearBuilt, property.year_built?.toString() ?? ""],
    [p.condition, property.condition ? dict.listing.conditions[property.condition] : ""],
    [p.furnishing, property.furnishing ? dict.listing.furnishing[property.furnishing] : ""],
    [
      p.ownership,
      property.ownership_document !== "UNKNOWN"
        ? `${dict.listing.ownership[property.ownership_document]} ${p.declared}`
        : "",
    ],
    [p.published, formatDate(property.published_at, locale) ?? ""],
  ];
  const shownFacts = facts.filter(([, value]) => value !== "");

  // The three numbers people scan first, shown large under the title.
  const keyStats: [string, string][] = (
    [
      [dict.listing.area, formatArea(property.area_m2, locale) ?? ""],
      [dict.listing.bedrooms, property.bedrooms?.toString() ?? ""],
      [dict.listing.bathrooms, property.bathrooms?.toString() ?? ""],
    ] as [string, string][]
  ).filter(([, v]) => v !== "");

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      {property.status === "APPROVED" && <ViewBeacon propertyId={property.id} />}
      {property.status !== "APPROVED" && (
        <Alert tone="info">{dict.listing.statuses[property.status]}</Alert>
      )}

      <Gallery media={property.media} title={title} emptyLabel={dict.listing.noImage} />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-12">
        <div className="flex min-w-0 flex-col">
          <header className="flex flex-col gap-3 pb-8">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full bg-accent-tint px-2.5 py-1 font-medium text-accent">
                {dict.listing.purposes[property.purpose]}
              </span>
              {property.verified && (
                <span className="rounded-full bg-success/15 px-2.5 py-1 font-medium text-success">
                  ✓ {dict.listing.verified}
                </span>
              )}
              {property.is_demo && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
              <span className="text-ink-3 tabular" dir="ltr">
                {property.reference_code}
              </span>
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              {title}
            </h1>
            <p className="text-ink-2">{where}</p>
            {property.is_demo && <p className="text-sm text-ink-3">{p.demoBanner}</p>}
            {keyStats.length > 0 && (
              <dl className="mt-3 flex flex-wrap gap-x-10 gap-y-3">
                {keyStats.map(([k, v]) => (
                  <div key={k}>
                    <dd className="font-display text-2xl font-semibold text-ink tabular">{v}</dd>
                    <dt className="text-sm text-ink-3">{k}</dt>
                  </div>
                ))}
              </dl>
            )}
          </header>

          <Section title={p.facts}>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
              {shownFacts.map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-ink-3">{k}</dt>
                  <dd className="mt-0.5 font-medium text-ink tabular">{v}</dd>
                </div>
              ))}
            </dl>
          </Section>

          {description && (
            <Section title={p.description}>
              <p className="max-w-[68ch] leading-8 whitespace-pre-line text-ink">{description}</p>
            </Section>
          )}

          {property.amenities.length > 0 && (
            <Section title={p.amenities}>
              <ul className="flex flex-wrap gap-2 text-sm">
                {property.amenities.map((code) => (
                  <li key={code} className="rounded-full bg-fill px-3 py-1.5 text-ink">
                    {label(amenities, code)}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title={p.location}>
            <p className="font-medium text-ink">{where}</p>
            {property.street && <p className="text-sm text-ink-2">{property.street}</p>}
            {property.address_text && <p className="text-sm text-ink-2">{property.address_text}</p>}
            {property.location_privacy !== "EXACT" && (
              <p className="mt-2 text-xs text-ink-3">
                {property.location_privacy === "HIDDEN" ? p.hiddenNote : p.approximateNote}
              </p>
            )}
          </Section>

          <div className="flex flex-col gap-6 border-t border-hairline py-8">
            {property.status === "APPROVED" && (
              <IntelligencePanel dict={dict} locale={locale} propertyId={property.id} />
            )}
            {property.status === "APPROVED" && (
              <PropertySummary dict={dict} locale={locale} propertyId={property.id} />
            )}
            {property.status === "APPROVED" && (
              <Insights
                propertyId={property.id}
                purpose={property.purpose}
                dict={dict}
                locale={locale}
              />
            )}
            <Nearby propertyId={property.id} dict={dict} locale={locale} />
          </div>

          {history.length > 1 && (
            <Section title={p.priceHistory}>
              <ol className="flex flex-col gap-2 text-sm">
                {history.map((h, i) => (
                  <li key={i} className="flex justify-between gap-3 tabular">
                    <span className="text-ink-3">{formatDate(h.changed_at, locale)}</span>
                    <span className="font-medium text-ink">
                      {h.price_on_request
                        ? dict.listing.priceOnRequest
                        : formatPrice(h.price_amount, h.currency, locale)}
                    </span>
                  </li>
                ))}
              </ol>
            </Section>
          )}
        </div>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
          <div className="rounded-[var(--radius-card)] bg-surface p-6 shadow-float ring-1 ring-hairline">
            <p className="font-display text-3xl font-semibold tracking-tight text-ink tabular">
              {price}
            </p>
            {property.negotiable && (
              <p className="mt-1 text-sm text-ink-3">{dict.listing.negotiable}</p>
            )}
            {conversion?.converted && conversion.rate && (
              <p className="mt-1 text-sm text-ink-3 tabular">
                ≈ {formatPrice(conversion.converted, conversion.to, locale)} (
                {dict.money.indicative}
                {" — "}
                {dict.money.indicativeNote} {conversion.rate.source},{" "}
                {formatDate(conversion.rate.effective_at, locale)})
              </p>
            )}

            <div className="mt-5 border-t border-hairline pt-5">
              <p className="text-xs text-ink-3">{p.by}</p>
              <p className="font-semibold text-ink">
                {property.lister.name}
                {property.lister.kind === "agency" && property.lister.agency_verified && (
                  <span className="ms-1 text-success">✓</span>
                )}
              </p>
              <div className="mt-4 flex flex-col gap-2">
                {property.lister.phone ? (
                  <a
                    href={`tel:${property.lister.phone}`}
                    dir="ltr"
                    className="inline-flex h-12 items-center justify-center rounded-full bg-accent-fill px-5 font-medium text-white transition hover:bg-accent-fill-hover"
                  >
                    {p.call} {property.lister.phone}
                  </a>
                ) : (
                  <p className="text-sm text-ink-3">{p.contactHidden}</p>
                )}
                {property.lister.whatsapp && (
                  <a
                    href={`https://wa.me/${property.lister.whatsapp.replace(/\D/g, "")}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex h-12 items-center justify-center rounded-full px-5 font-medium text-success ring-1 ring-inset ring-success/50 transition hover:bg-success/10"
                  >
                    {p.whatsapp}
                  </a>
                )}
              </div>
            </div>

            {!property.can_edit && property.status === "APPROVED" && (
              <div className="mt-5 border-t border-hairline pt-5">
                <h2 className="mb-3 font-semibold text-ink">{dict.inquiry.title}</h2>
                <InquiryForm
                  dict={dict}
                  propertyId={property.id}
                  signedIn={!!me}
                  defaultName={me?.user.full_name ?? ""}
                  defaultPhone={me?.user.phone ?? ""}
                  defaultEmail={me?.user.email ?? ""}
                />
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <FavoriteButton
              variant="button"
              propertyId={property.id}
              initial={favorites.has(property.id)}
              signedIn={!!me}
              labels={{ save: p.save, saved: p.saved, loginToSave: p.loginToSave }}
            />
            <ShareButton label={p.share} copied={p.copied} />
            {property.can_edit && (
              <Link
                href={`/dashboard/properties/${property.id}`}
                className="inline-flex h-10 items-center rounded-full px-4 text-sm font-medium text-ink ring-1 ring-inset ring-hairline hover:bg-fill"
              >
                {dict.myListings.edit}
              </Link>
            )}
          </div>

          {me && !property.can_edit && property.status === "APPROVED" && (
            <ReportButton dict={dict} targetType="PROPERTY" targetId={property.id} />
          )}

          <section className="rounded-[var(--radius-card)] bg-fill p-5">
            <h2 className="text-sm font-semibold text-ink">{p.verification}</h2>
            <p className="mt-1 text-sm text-ink-2">
              {property.verified ? p.verifiedText : p.notVerifiedText}
            </p>
            {verifications.length > 0 && (
              <ul className="mt-3 flex flex-col gap-1.5 text-sm">
                {verifications.map((v) => (
                  <li key={v.id} className="flex justify-between gap-3">
                    <span className="text-ink">{p.checks[v.kind]}</span>
                    <span className={v.result === "PASSED" ? "text-success" : "text-danger"}>
                      {v.result === "PASSED" ? p.passed : p.failed}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

/** A calm page section: heading and content separated by a hairline, no box. */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-hairline py-8">
      <h2 className="mb-4 font-display text-xl font-semibold tracking-tight text-ink">{title}</h2>
      {children}
    </section>
  );
}
