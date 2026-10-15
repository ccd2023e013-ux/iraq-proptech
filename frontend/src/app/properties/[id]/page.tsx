import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { Alert } from "@/components/ui/Alert";
import { Icon, type IconName } from "@/components/ui/Icon";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { Insights } from "@/features/ai/Insights";
import { IntelligencePanel } from "@/features/ai/IntelligencePanel";
import { PropertySummary } from "@/features/ai/PropertySummary";
import { ReportButton } from "@/features/admin/ReportButton";
import { ViewBeacon } from "@/features/analytics/ViewBeacon";
import { InquiryForm } from "@/features/crm/InquiryForm";
import { FavoriteButton } from "@/features/properties/FavoriteButton";
import { type ApartmentMedian, FutureScenarios } from "@/features/properties/FutureScenarios";
import { Gallery, ShareButton } from "@/features/properties/Gallery";
import { MapPreview } from "@/features/map/MapPreview";
import { Nearby } from "@/features/properties/Nearby";
import { favoriteIds } from "@/features/search/data";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { formatArea, formatDate, formatPrice, placeName } from "@/lib/format";
import { formatBbox } from "@/lib/map/geo";
import { bboxAround } from "@/lib/map/places";
import { resolveMapConfig } from "@/lib/map/provider";
import { stagger } from "@/lib/motion";
import type { MarketReport } from "@/types/market";
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
  const mapConfig = resolveMapConfig(process.env);
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
  const keyStats: [string, string, IconName][] = (
    [
      [dict.listing.area, formatArea(property.area_m2, locale) ?? "", "area"],
      [dict.listing.bedrooms, property.bedrooms?.toString() ?? "", "bed"],
      [dict.listing.bathrooms, property.bathrooms?.toString() ?? "", "bath"],
    ] as [string, string, IconName][]
  ).filter(([, v]) => v !== "");

  // Future scenarios: plots and houses with a known area, priced against the
  // market report's apartment median for the city (when there is one).
  const plotM2 = Number(property.land_area_m2 ?? property.area_m2 ?? 0);
  const scenarioTypes = ["LAND", "HOUSE", "VILLA", "FARM"];
  const showScenarios = plotM2 >= 60 && scenarioTypes.includes(property.property_type_code);
  const cityReport = showScenarios
    ? await serverApiFetch<MarketReport>(
        `/api/v1/market/report?city_id=${property.city.id}&language=${locale}&include_demo=true`,
      ).catch(() => null)
    : null;
  const aptSeg = cityReport?.segments.find(
    (seg) =>
      seg.property_type_code === "APARTMENT" && seg.purpose === "SALE" && seg.median_price_per_m2,
  );
  const median: ApartmentMedian | null = aptSeg
    ? {
        perM2: Number(aptSeg.median_price_per_m2),
        currency: aptSeg.currency,
        listings: aptSeg.listings,
        demo: !!cityReport?.provenance.includes_demo,
        area: placeName(property.city, locale) ?? "",
      }
    : null;
  const representative = property.media.some((m) => m.caption?.includes("صورة تمثيلية"));
  const v = p.provenance;
  const passed = verifications.filter((x) => x.result === "PASSED").map((x) => x.kind);
  const documentChecked = passed.includes("DOCUMENT") || passed.includes("OWNERSHIP");
  const mapHref = property.display_location
    ? `/map?bbox=${formatBbox(bboxAround(property.display_location.lon, property.display_location.lat, 1.5))}&selected=${property.id}`
    : "/map";
  const areaName =
    (locale === "en" && property.district?.name_en) ||
    property.district?.name_ar ||
    (locale === "en" && property.city.name_en) ||
    property.city.name_ar;

  return (
    <div data-vt-ready={property.id} className="flex flex-col pb-28 md:pb-12">
      {property.status === "APPROVED" && <ViewBeacon propertyId={property.id} />}

      {/* Title band: where we are, what it is, what it costs. */}
      <div className="page flex flex-col gap-6 pt-6 pb-6 md:pt-10">
        {property.status !== "APPROVED" && (
          <Alert tone="info">{dict.listing.statuses[property.status]}</Alert>
        )}
        <nav aria-label={p.location} className="meta flex flex-wrap items-center gap-1.5">
          <Link href={mapHref} className="inline-flex items-center gap-1.5 hover:text-ink">
            <Icon name="map" className="size-4 text-spatial" />
            {p.backToMap}
          </Link>
          <Icon name="chevron" className="size-3.5 opacity-60" />
          <Link href={`/properties?city_id=${property.city.id}`} className="hover:text-ink">
            {placeName(property.city, locale)}
          </Link>
          {property.district && (
            <>
              <Icon name="chevron" className="size-3.5 opacity-60" />
              <span>{placeName(property.district, locale)}</span>
            </>
          )}
        </nav>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between lg:gap-12">
          <div className="reveal flex min-w-0 flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-[var(--radius-tag)] bg-fill px-2.5 py-1 text-[13px] font-medium text-ink">
                {dict.listing.purposes[property.purpose]}
              </span>
              <span className="rounded-[var(--radius-tag)] bg-fill px-2.5 py-1 text-[13px] text-ink-2">
                {label(types, property.property_type_code)}
              </span>
              {property.verified && (
                <span className="inline-flex items-center gap-1 rounded-[var(--radius-tag)] bg-accent-tint px-2.5 py-1 text-[13px] font-medium text-accent">
                  <Icon name="check" className="size-3.5" strokeWidth={2.2} />
                  {dict.listing.verified}
                </span>
              )}
              {property.is_demo && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
              <span className="caption tabular" dir="ltr">
                {property.reference_code}
              </span>
            </div>
            <h1 className="display-lg max-w-[22ch] text-ink">{title}</h1>
            <p className="flex items-center gap-1.5 text-[17px] text-ink-2">
              <Icon name="pin" className="size-[18px] shrink-0 text-spatial" />
              {where}
            </p>
          </div>
          <div
            className="reveal flex shrink-0 flex-col gap-1 lg:items-end lg:text-end"
            style={stagger(1)}
          >
            <p className="kpi text-[2.25rem] leading-none text-ink md:text-[2.75rem]">{price}</p>
            <p className="meta">
              {property.negotiable
                ? dict.listing.negotiable
                : dict.listing.purposes[property.purpose]}
            </p>
            {conversion?.converted && conversion.rate && (
              <p className="caption tabular">
                ≈ {formatPrice(conversion.converted, conversion.to, locale)} ·{" "}
                {dict.money.indicative} ({conversion.rate.source},{" "}
                {formatDate(conversion.rate.effective_at, locale)})
              </p>
            )}
          </div>
        </div>
      </div>

      {/* The property itself: photography first. */}
      <div className="page reveal" style={stagger(2)}>
        <Gallery
          media={property.media}
          title={title}
          emptyLabel={dict.listing.noImage}
          labels={{ prev: p.prevPhoto, next: p.nextPhoto }}
          creditsLabel={dict.footer.photoCredits}
          transitionName="property-photo"
          stamp={
            property.is_demo && representative
              ? `${dict.listing.demo} · ${v.photosRepresentative}`
              : undefined
          }
        />
      </div>

      {/* Key facts: the numbers people scan first, as one band. */}
      {keyStats.length > 0 && (
        <div className="page">
          <dl
            aria-label={p.keyFacts}
            className="mt-6 grid grid-cols-2 overflow-hidden rounded-[var(--radius-card)] bg-hairline [gap:1px] sm:grid-cols-4"
          >
            {[
              ...keyStats,
              ...((property.floors
                ? [[p.floors, String(property.floors), "building"]]
                : property.year_built
                  ? [[p.yearBuilt, String(property.year_built), "calendar"]]
                  : []) as [string, string, IconName][]),
            ]
              .slice(0, 4)
              .map(([k, val, icon]) => (
                <div key={k} className="flex items-center gap-4 bg-surface px-5 py-5">
                  <Icon name={icon} className="size-6 shrink-0 text-ink-3" strokeWidth={1.6} />
                  <div className="min-w-0">
                    <dd className="kpi truncate text-2xl text-ink">{val}</dd>
                    <dt className="meta">{k}</dt>
                  </div>
                </div>
              ))}
          </dl>
        </div>
      )}

      <div className="page mt-4 grid gap-x-14 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-w-0 flex-col">
          {/* Provenance: verified vs declared vs demo, stated once, plainly. */}
          <Section title={v.title} lede={v.lede}>
            <dl className="grid gap-px overflow-hidden rounded-[var(--radius-card)] bg-hairline sm:grid-cols-2">
              <Provenance
                label={v.listing}
                value={property.verified ? v.listingVerified : v.listingDeclared}
                tone={property.verified ? "verified" : "declared"}
              />
              <Provenance
                label={v.photos}
                value={
                  !property.media.length
                    ? dict.listing.noImage
                    : representative
                      ? v.photosRepresentative
                      : v.photosLister
                }
                tone={representative ? "demo" : "declared"}
              />
              <Provenance
                label={v.location}
                value={
                  property.location_privacy === "EXACT"
                    ? v.locationExact
                    : property.location_privacy === "HIDDEN"
                      ? v.locationHidden
                      : v.locationApprox
                }
                tone={property.location_privacy === "EXACT" ? "declared" : "estimate"}
              />
              <Provenance
                label={v.checks}
                value={
                  verifications.length
                    ? verifications
                        .map(
                          (c) =>
                            `${p.checks[c.kind]}: ${c.result === "PASSED" ? p.passed : p.failed}`,
                        )
                        .join(" · ")
                    : v.noChecks
                }
                tone={passed.length ? "verified" : "declared"}
              />
              {property.is_demo && (
                <div className="flex items-start gap-3 bg-gold-100 px-5 py-4 sm:col-span-2">
                  <Icon name="info" className="mt-0.5 size-5 shrink-0 text-gold-700" />
                  <div>
                    <dt className="font-medium text-ink">{v.demo}</dt>
                    <dd className="text-sm text-ink-2">{p.demoBanner}</dd>
                  </div>
                </div>
              )}
            </dl>
          </Section>

          {description && (
            <Section title={p.description}>
              <p className="max-w-[68ch] text-[17px] leading-8 whitespace-pre-line text-ink">
                {description}
              </p>
            </Section>
          )}

          <Section title={p.facts}>
            <FactGrid facts={shownFacts} />
          </Section>

          {property.amenities.length > 0 && (
            <Section title={p.amenities}>
              <ul className="grid grid-cols-2 gap-x-6 gap-y-3 text-[15px] sm:grid-cols-3">
                {property.amenities.map((code) => (
                  <li key={code} className="flex items-center gap-2.5 text-ink">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full bg-accent-tint text-accent">
                      <Icon name="check" className="size-3.5" strokeWidth={2.4} />
                    </span>
                    {label(amenities, code)}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title={p.documents}>
            {property.ownership_document === "UNKNOWN" ? (
              <p className="text-ink-2">{p.documentNone}</p>
            ) : (
              <div className="flex items-start gap-4 rounded-[var(--radius-card)] bg-surface p-5 shadow-[inset_0_0_0_1px_var(--hairline)]">
                <span className="grid size-11 shrink-0 place-items-center rounded-[var(--radius-control)] bg-fill text-ink-2">
                  <Icon name="document" className="size-5" />
                </span>
                <div className="flex min-w-0 flex-col gap-1">
                  <p className="meta">{p.documentDeclared}</p>
                  <p className="font-medium text-ink">
                    {dict.listing.ownership[property.ownership_document]}
                  </p>
                  <p className={`text-sm ${documentChecked ? "text-accent" : "text-ink-2"}`}>
                    {documentChecked ? p.documentChecked : p.documentNotChecked}
                  </p>
                </div>
              </div>
            )}
          </Section>

          <Section title={p.location}>
            {property.display_location && property.location_privacy !== "HIDDEN" ? (
              <div className="flex flex-col gap-4">
                <MapPreview
                  config={mapConfig}
                  className="h-72 sm:h-96"
                  points={[
                    {
                      lat: property.display_location.lat,
                      lon: property.display_location.lon,
                      precision: property.location_privacy === "EXACT" ? "exact" : "area",
                    },
                  ]}
                  label={`${p.location}: ${where}`}
                />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-ink">{where}</p>
                    {property.street && <p className="text-sm text-ink-2">{property.street}</p>}
                    {property.location_privacy !== "EXACT" && (
                      <p className="caption mt-1">{p.approximateNote}</p>
                    )}
                  </div>
                  <Link href={mapHref} className="btn btn-secondary btn-sm">
                    <Icon name="map" className="size-4 text-spatial" />
                    {p.openOnMap}
                  </Link>
                </div>
              </div>
            ) : (
              <p className="text-ink-2">{p.hiddenNote}</p>
            )}
            <div className="mt-8">
              <Nearby propertyId={property.id} dict={dict} locale={locale} />
            </div>
          </Section>

          {showScenarios && (
            <Section title={dict.scenarios.title} lede={dict.scenarios.lede}>
              <FutureScenarios
                dict={dict}
                locale={locale}
                propertyId={property.id}
                plotM2={plotM2}
                floorsNow={property.floors}
                median={median}
              />
            </Section>
          )}

          {history.length > 1 && (
            <Section title={p.priceHistory} lede={p.priceHistoryNote}>
              <PriceHistoryChart history={history} locale={locale} />
            </Section>
          )}

          {property.status === "APPROVED" && (
            <Section title={p.intelligence} lede={p.intelligenceLede}>
              <div className="flex flex-col gap-6">
                <IntelligencePanel dict={dict} locale={locale} propertyId={property.id} />
                <PropertySummary dict={dict} locale={locale} propertyId={property.id} />
                <Insights
                  propertyId={property.id}
                  purpose={property.purpose}
                  dict={dict}
                  locale={locale}
                />
                <div className="flex flex-wrap gap-3">
                  <Link
                    href={
                      property.district
                        ? `/market?district_id=${property.district.id}&city_id=${property.city.id}`
                        : `/market?city_id=${property.city.id}`
                    }
                    className="btn btn-secondary btn-sm"
                    data-testid="area-market-link"
                  >
                    <Icon name="chart" className="size-4 text-spatial" />
                    {dict.market.seeArea}: {areaName}
                  </Link>
                  <Link
                    href={`/vision?property_id=${property.id}`}
                    className="btn btn-secondary btn-sm"
                    data-testid="vision-link"
                  >
                    <Icon name="insight" className="size-4 text-accent" />
                    {dict.vision.title}
                  </Link>
                  {property.display_location && property.location_privacy !== "HIDDEN" && (
                    <Link
                      href={`/properties/${property.id}/flight`}
                      className="btn btn-secondary btn-sm"
                      data-testid="flight-link"
                    >
                      <Icon name="video" className="size-4 text-spatial" />
                      {dict.flight.open}
                    </Link>
                  )}
                </div>
              </div>
            </Section>
          )}
        </div>

        {/* Contact: always at hand on wide screens; a bar on phones. */}
        <aside className="flex flex-col gap-4 pt-8 lg:sticky lg:top-[calc(var(--header-h)+1.5rem)] lg:self-start">
          <div id="contact" className="surface-focus scroll-mt-24 rounded-[var(--radius-card)] p-6">
            <p className="meta">{p.by}</p>
            <p className="mt-1 flex items-center gap-1.5 text-lg font-semibold text-ink">
              {property.lister.name}
              {property.lister.kind === "agency" && property.lister.agency_verified && (
                <Icon name="check" className="size-4 text-accent" strokeWidth={2.2} />
              )}
            </p>
            <div className="mt-5 flex flex-col gap-2">
              {property.lister.phone ? (
                <a
                  href={`tel:${property.lister.phone}`}
                  dir="ltr"
                  className="btn btn-primary btn-lg"
                >
                  {p.call} {property.lister.phone}
                </a>
              ) : (
                <p className="text-sm text-ink-2">{p.contactHidden}</p>
              )}
              {property.lister.whatsapp && (
                <a
                  href={`https://wa.me/${property.lister.whatsapp.replace(/\D/g, "")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary"
                >
                  {p.whatsapp}
                </a>
              )}
            </div>
            {!property.can_edit && property.status === "APPROVED" && (
              <div className="mt-6 border-t border-hairline pt-5">
                <h2 className="title mb-3 text-ink">{dict.inquiry.title}</h2>
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
                href={`/studio?property_id=${property.id}`}
                className="btn btn-secondary btn-sm"
                data-testid="studio-link"
              >
                {dict.studio.title}
              </Link>
            )}
            {property.can_edit && (
              <Link
                href={`/dashboard/properties/${property.id}`}
                className="btn btn-secondary btn-sm"
              >
                {dict.myListings.edit}
              </Link>
            )}
          </div>

          {me && !property.can_edit && property.status === "APPROVED" && (
            <ReportButton dict={dict} targetType="PROPERTY" targetId={property.id} />
          )}
        </aside>
      </div>

      {/* Phones: price and contact stay within reach above the tab bar. */}
      <div className="fixed inset-x-0 bottom-[var(--tabbar-h)] z-[var(--z-float)] flex items-center justify-between gap-3 border-t border-hairline bg-canvas/90 px-4 py-3 backdrop-blur-xl md:hidden">
        <p className="kpi min-w-0 truncate text-xl text-ink">{price}</p>
        <a href="#contact" className="btn btn-primary shrink-0">
          {p.contactCta}
        </a>
      </div>
    </div>
  );
}

type Tone = "verified" | "declared" | "demo" | "estimate";

/** One provenance row: what kind of statement a part of the page is. */
function Provenance({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  const dot: Record<Tone, string> = {
    verified: "bg-accent-fill",
    declared: "bg-ink-3",
    demo: "bg-gold-500",
    estimate: "bg-spatial-fill",
  };
  return (
    <div className="flex items-start gap-3 bg-surface px-5 py-4">
      <span aria-hidden className={`mt-2 size-2 shrink-0 rounded-full ${dot[tone]}`} />
      <div className="min-w-0">
        <dt className="meta">{label}</dt>
        <dd className="mt-0.5 text-[15px] text-ink">{value}</dd>
      </div>
    </div>
  );
}

/** Asking price over time (one currency), as a step line with its dates. */
function PriceHistoryChart({ history, locale }: { history: PricePoint[]; locale: "ar" | "en" }) {
  const currency = history[history.length - 1]?.currency ?? "IQD";
  const rows = history
    .filter((h) => !h.price_on_request && h.price_amount && h.currency === currency)
    .map((h) => ({
      t: new Date(h.changed_at).getTime(),
      v: Number(h.price_amount),
      at: h.changed_at,
    }))
    .filter((r) => Number.isFinite(r.v))
    .sort((a, b) => a.t - b.t);
  if (rows.length < 2) return null;
  const W = 640;
  const H = 180;
  const pad = { x: 12, top: 28, bottom: 28 };
  const t0 = rows[0]!.t;
  const t1 = Math.max(rows[rows.length - 1]!.t, t0 + 1);
  const lo = Math.min(...rows.map((r) => r.v));
  const hi = Math.max(...rows.map((r) => r.v));
  const span = hi - lo || hi || 1;
  const x = (t: number) => pad.x + ((t - t0) / (t1 - t0)) * (W - pad.x * 2);
  const y = (v: number) => pad.top + (1 - (v - lo) / span) * (H - pad.top - pad.bottom);
  let d = `M ${x(rows[0]!.t)} ${y(rows[0]!.v)}`;
  for (let i = 1; i < rows.length; i++) {
    d += ` H ${x(rows[i]!.t)} V ${y(rows[i]!.v)}`;
  }
  const last = rows[rows.length - 1]!;
  return (
    <figure className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-44 w-full overflow-visible text-spatial"
        role="img"
        aria-label={rows
          .map((r) => `${formatDate(r.at, locale)}: ${formatPrice(String(r.v), currency, locale)}`)
          .join("; ")}
      >
        <line
          x1={pad.x}
          x2={W - pad.x}
          y1={H - pad.bottom}
          y2={H - pad.bottom}
          className="stroke-hairline"
        />
        <path d={d} fill="none" stroke="currentColor" strokeWidth={2} strokeLinejoin="round" />
        {rows.map((r) => (
          <circle
            key={r.t}
            cx={x(r.t)}
            cy={y(r.v)}
            r={3.5}
            className="fill-canvas"
            stroke="currentColor"
            strokeWidth={2}
          />
        ))}
        <text
          x={x(last.t)}
          y={y(last.v) - 10}
          textAnchor="end"
          className="fill-ink text-[13px] font-semibold"
        >
          {formatPrice(String(last.v), currency, locale)}
        </text>
      </svg>
      <figcaption className="caption flex justify-between tabular">
        <span>{formatDate(rows[0]!.at, locale)}</span>
        <span>{formatDate(last.at, locale)}</span>
      </figcaption>
    </figure>
  );
}

function FactGrid({ facts }: { facts: [string, string][] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
      {facts.map(([k, v]) => (
        <div key={k}>
          <dt className="meta">{k}</dt>
          <dd className="mt-0.5 font-medium text-ink tabular">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A calm page section: heading (and an optional lede), no box. */
function Section({ title, lede, children }: { title: string; lede?: string; children: ReactNode }) {
  return (
    <section className="border-t border-hairline py-10 first:border-t-0">
      <div className="mb-5 flex flex-col gap-1">
        <h2 className="title text-ink">{title}</h2>
        {lede && <p className="meta">{lede}</p>}
      </div>
      {children}
    </section>
  );
}
