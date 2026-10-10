import type { Metadata } from "next";
import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";
import { Card } from "@/components/ui/Card";
import { ProviderBadge } from "@/features/ai/ProviderBadge";
import { errorMessage, getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { formatArea, formatPrice } from "@/lib/format";
import { first, type RawParams } from "@/lib/search";
import type { AIEnvelope } from "@/types/ai";
import type { Property, ReferenceItem } from "@/types/property";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.compare.title, robots: { index: false } };
}

interface AICompare {
  properties: {
    id: string;
    currency: string;
    price_per_m2: string | null;
    local_median_per_m2: string | null;
    vs_local_median_percent: number | null;
  }[];
  prices_comparable: boolean;
  highlights: {
    lowest_price_per_m2: string | null;
    largest_area: string | null;
    most_bedrooms: string | null;
  };
}

interface Comparison {
  items: Property[];
  price_per_m2: (string | null)[];
  rows: { field: string; values: (string | null)[]; differs: boolean }[];
  same_currency: boolean;
  cheapest_per_m2_id: string | null;
  amenities_common: string[];
}

export default async function ComparePage({ searchParams }: { searchParams: Promise<RawParams> }) {
  const params = await searchParams;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const c = dict.compare;
  const ids = (first(params.ids) ?? "").split(",").filter(Boolean);
  if (ids.length < 2) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <EmptyState
          title={c.title}
          body={c.needTwo}
          glyph="grid"
          action={{ href: "/properties", label: dict.nav.properties }}
        />
      </div>
    );
  }
  let data: Comparison;
  try {
    data = await serverApiFetch<Comparison>(
      `/api/v1/properties/compare?ids=${encodeURIComponent(ids.join(","))}`,
    );
  } catch (error) {
    const code = error instanceof ApiError ? error.code : "UNKNOWN";
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <Alert tone="error">{errorMessage(dict, code)}</Alert>
      </div>
    );
  }
  const [types, amenities, analysis] = await Promise.all([
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/amenities"),
    serverApiFetch<AIEnvelope<AICompare>>(
      `/api/v1/ai/compare?ids=${encodeURIComponent(ids.slice(0, 4).join(","))}`,
    ).catch(() => null),
  ]);
  const label = (items: ReferenceItem[], code: string) => {
    const item = items.find((i) => i.code === code);
    return item ? (locale === "ar" ? item.name_ar : item.name_en) : code;
  };
  const show = (field: string, value: string | null, p: Property): string => {
    if (value === null || value === "") return c.notProvided;
    switch (field) {
      case "property_type_code":
        return label(types, value);
      case "purpose":
        return dict.listing.purposes[p.purpose];
      case "price_amount":
        return p.price_on_request
          ? dict.listing.priceOnRequest
          : (formatPrice(value, p.currency, locale) ?? value);
      case "area_m2":
      case "land_area_m2":
        return formatArea(value, locale) ?? value;
      case "condition":
        return p.condition ? dict.listing.conditions[p.condition] : value;
      case "furnishing":
        return p.furnishing ? dict.listing.furnishing[p.furnishing] : value;
      case "ownership_document":
        return value === "UNKNOWN" ? c.notProvided : dict.listing.ownership[p.ownership_document];
      case "verified":
        return value === "True" ? `✓ ${dict.listing.verified}` : "—";
      default:
        return value;
    }
  };
  const fieldLabel: Record<string, string> = {
    property_type_code: dict.property.type,
    purpose: dict.property.purpose,
    price_amount: dict.listingForm.price,
    currency: dict.listingForm.currency,
    area_m2: dict.listing.area,
    land_area_m2: dict.listing.landArea,
    bedrooms: dict.listing.bedrooms,
    bathrooms: dict.listing.bathrooms,
    floors: dict.property.floors,
    year_built: dict.property.yearBuilt,
    condition: dict.property.condition,
    furnishing: dict.property.furnishing,
    ownership_document: dict.property.ownership,
    verified: dict.listing.verified,
  };
  const title = (p: Property) => (locale === "en" && p.title_en ? p.title_en : p.title_ar);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 sm:px-6">
      <h1 className="display-md text-ink">{c.title}</h1>
      {!data.same_currency && <Alert tone="info">{c.differentCurrencies}</Alert>}
      <div className="overflow-x-auto surface-1 rounded-[var(--radius-card)]">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-sand-200">
              <th className="p-3 text-start" />
              {data.items.map((p) => (
                <th key={p.id} scope="col" className="p-3 text-start align-top">
                  <Link
                    href={`/properties/${p.id}`}
                    className="font-semibold text-brand-800 hover:underline"
                  >
                    {title(p)}
                  </Link>
                  {p.is_demo && <span className="ms-1 text-xs font-bold text-warning">DEMO</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr
                key={row.field}
                className={`border-b border-sand-100 ${row.differs ? "bg-gold-100/40" : ""}`}
              >
                <th scope="row" className="p-3 text-start font-medium text-sand-700">
                  {fieldLabel[row.field] ?? row.field}
                </th>
                {row.values.map((v, i) => (
                  <td key={i} className="p-3 tabular">
                    {show(row.field, v, data.items[i] as Property)}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="border-b border-sand-100">
              <th scope="row" className="p-3 text-start font-medium text-sand-700">
                {c.pricePerM2}
              </th>
              {data.price_per_m2.map((v, i) => {
                const p = data.items[i] as Property;
                return (
                  <td key={p.id} className="p-3 tabular">
                    {v ? formatPrice(v, p.currency, locale) : c.notProvided}
                    {data.cheapest_per_m2_id === p.id && (
                      <span className="ms-2 rounded bg-success px-1.5 py-0.5 text-xs text-white">
                        {c.cheapest}
                      </span>
                    )}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
      {analysis && (
        <Card title={`${dict.ai.compareAnalysis} · ${dict.ai.badge}`}>
          <div className="flex flex-col gap-3 text-sm" data-testid="ai-compare">
            <ProviderBadge dict={dict} provider={analysis.provider} model={analysis.model} />
            {!analysis.result.prices_comparable && (
              <p className="text-sand-700">{dict.ai.notComparable}</p>
            )}
            <ul className="flex flex-col gap-2">
              {analysis.result.properties.map((row) => {
                const p = data.items.find((i) => i.id === row.id);
                if (!p) return null;
                const tags = [
                  analysis.result.highlights.lowest_price_per_m2 === row.id &&
                    dict.ai.cheapestPerM2,
                  analysis.result.highlights.largest_area === row.id && dict.ai.largest,
                  analysis.result.highlights.most_bedrooms === row.id && dict.ai.mostBedrooms,
                ].filter(Boolean);
                return (
                  <li key={row.id} className="rounded-md border border-sand-200 p-3">
                    <p className="font-semibold text-sand-900">{title(p)}</p>
                    <p className="tabular text-sand-700">
                      {dict.ai.pricePerM2}:{" "}
                      {row.price_per_m2
                        ? formatPrice(row.price_per_m2, p.currency, locale)
                        : c.notProvided}
                      {row.vs_local_median_percent !== null && (
                        <span className="ms-2 text-xs text-sand-500">
                          ({dict.ai.vsCityMedian}: {row.vs_local_median_percent > 0 ? "+" : ""}
                          {row.vs_local_median_percent}%)
                        </span>
                      )}
                    </p>
                    {tags.length > 0 && (
                      <p className="mt-1 flex flex-wrap gap-1">
                        {tags.map((t) => (
                          <span
                            key={String(t)}
                            className="rounded bg-sand-100 px-1.5 py-0.5 text-xs text-success"
                          >
                            {t}
                          </span>
                        ))}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
            <p className="text-xs text-sand-500">{analysis.methodology}</p>
          </div>
        </Card>
      )}
      {data.amenities_common.length > 0 && (
        <p className="text-sm text-sand-700">
          {c.commonAmenities}: {data.amenities_common.map((a) => label(amenities, a)).join("، ")}
        </p>
      )}
    </div>
  );
}
