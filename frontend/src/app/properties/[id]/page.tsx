import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Insights } from "@/features/ai/Insights";
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

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6">
      {property.status === "APPROVED" && <ViewBeacon propertyId={property.id} />}
      {property.is_demo && <Alert tone="warning">{p.demoBanner}</Alert>}
      {property.status !== "APPROVED" && (
        <Alert tone="info">{dict.listing.statuses[property.status]}</Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="flex flex-col gap-6">
          <Gallery media={property.media} title={title} emptyLabel={dict.listing.noImage} />

          <header className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-md bg-brand-800 px-2 py-0.5 font-medium text-white">
                {dict.listing.purposes[property.purpose]}
              </span>
              {property.verified && (
                <span className="rounded-md bg-success px-2 py-0.5 font-medium text-white">
                  ✓ {dict.listing.verified}
                </span>
              )}
              <span className="font-mono text-sand-500" dir="ltr">
                {property.reference_code}
              </span>
            </div>
            <h1 className="text-2xl font-bold text-brand-900 sm:text-3xl">{title}</h1>
            <p className="text-sand-700">{where}</p>
            <p className="text-3xl font-bold text-brand-800 tabular">
              {price}
              {property.negotiable && (
                <span className="ms-2 text-sm font-normal text-sand-500">
                  ({dict.listing.negotiable})
                </span>
              )}
            </p>
            {conversion?.converted && conversion.rate && (
              <p className="text-sm text-sand-500 tabular">
                ≈ {formatPrice(conversion.converted, conversion.to, locale)} (
                {dict.money.indicative}
                {" — "}
                {dict.money.indicativeNote} {conversion.rate.source},{" "}
                {formatDate(conversion.rate.effective_at, locale)})
              </p>
            )}
          </header>

          <Card title={p.facts}>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
              {shownFacts.map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-sand-500">{k}</dt>
                  <dd className="font-medium text-sand-900 tabular">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>

          {description && (
            <Card title={p.description}>
              <p className="leading-8 whitespace-pre-line text-sand-900">{description}</p>
            </Card>
          )}

          {property.amenities.length > 0 && (
            <Card title={p.amenities}>
              <ul className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                {property.amenities.map((code) => (
                  <li key={code} className="flex items-center gap-2">
                    <span aria-hidden className="text-success">
                      ✓
                    </span>
                    {label(amenities, code)}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card title={p.location}>
            <p className="font-medium">{where}</p>
            {property.street && <p className="text-sm text-sand-700">{property.street}</p>}
            {property.address_text && (
              <p className="text-sm text-sand-700">{property.address_text}</p>
            )}
            <p className="mt-2 text-xs text-sand-500">
              {property.location_privacy === "HIDDEN"
                ? p.hiddenNote
                : property.location_privacy === "APPROXIMATE"
                  ? p.approximateNote
                  : null}
            </p>
          </Card>

          {property.status === "APPROVED" && (
            <Insights
              propertyId={property.id}
              purpose={property.purpose}
              dict={dict}
              locale={locale}
            />
          )}

          <Nearby propertyId={property.id} dict={dict} locale={locale} />

          {history.length > 1 && (
            <Card title={p.priceHistory}>
              <ol className="flex flex-col gap-2 text-sm">
                {history.map((h, i) => (
                  <li key={i} className="flex justify-between gap-3 tabular">
                    <span className="text-sand-500">{formatDate(h.changed_at, locale)}</span>
                    <span className="font-medium">
                      {h.price_on_request
                        ? dict.listing.priceOnRequest
                        : formatPrice(h.price_amount, h.currency, locale)}
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          )}
        </div>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-20 lg:self-start">
          <Card title={p.contact}>
            <p className="text-sm text-sand-500">{p.by}</p>
            <p className="font-semibold">
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
                  className="rounded-lg bg-brand-700 px-4 py-2.5 text-center font-medium text-white hover:bg-brand-800"
                >
                  {p.call} {property.lister.phone}
                </a>
              ) : (
                <p className="text-sm text-sand-500">{p.contactHidden}</p>
              )}
              {property.lister.whatsapp && (
                <a
                  href={`https://wa.me/${property.lister.whatsapp.replace(/\D/g, "")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-success px-4 py-2.5 text-center font-medium text-success"
                >
                  {p.whatsapp}
                </a>
              )}
            </div>
          </Card>

          {!property.can_edit && property.status === "APPROVED" && (
            <Card title={dict.inquiry.title}>
              <InquiryForm
                dict={dict}
                propertyId={property.id}
                signedIn={!!me}
                defaultName={me?.user.full_name ?? ""}
                defaultPhone={me?.user.phone ?? ""}
                defaultEmail={me?.user.email ?? ""}
              />
            </Card>
          )}

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
                className="rounded-lg border border-sand-200 px-4 py-2 text-sm font-medium"
              >
                {dict.myListings.edit}
              </Link>
            )}
          </div>

          {me && !property.can_edit && property.status === "APPROVED" && (
            <ReportButton dict={dict} targetType="PROPERTY" targetId={property.id} />
          )}

          <Card title={p.verification}>
            <p className="text-sm text-sand-700">
              {property.verified ? p.verifiedText : p.notVerifiedText}
            </p>
            {verifications.length > 0 && (
              <ul className="mt-3 flex flex-col gap-1.5 text-sm">
                {verifications.map((v) => (
                  <li key={v.id} className="flex justify-between gap-3">
                    <span>{p.checks[v.kind]}</span>
                    <span className={v.result === "PASSED" ? "text-success" : "text-danger"}>
                      {v.result === "PASSED" ? p.passed : p.failed}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
}
