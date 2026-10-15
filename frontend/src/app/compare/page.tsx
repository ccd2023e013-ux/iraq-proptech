import { PageHeader } from "@/components/ui/PageHeader";
import type { Metadata } from "next";
import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { SafeImage } from "@/components/ui/SafeImage";
import { ProviderBadge } from "@/features/ai/ProviderBadge";
import { errorMessage, getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { formatArea, formatPrice, placeName } from "@/lib/format";
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
      <div className="page flex flex-col pb-8">
        <PageHeader title={c.title} lede={c.lede} />
        <EmptyState
          title={c.needTwo}
          body={c.howToStart}
          glyph="compare"
          action={{ href: "/properties", label: c.browse }}
          secondary={{ href: "/map", label: c.openMap }}
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
  const onlyDiff = first(params.all) !== "1";
  const n = data.items.length;
  const cover = (p: Property) => p.media.find((m) => m.kind === "IMAGE");

  // Numeric rows get a magnitude bar and a "best" mark — only when the values
  // are comparable (same currency for money).
  type Rank = { better: "low" | "high"; money?: boolean };
  const RANK: Record<string, Rank> = {
    price_amount: { better: "low", money: true },
    area_m2: { better: "high" },
    land_area_m2: { better: "high" },
    bedrooms: { better: "high" },
    bathrooms: { better: "high" },
  };
  const numbers = (values: (string | null)[]) =>
    values.map((v) => (v === null || v === "" ? null : Number(v)));
  const bestIndex = (values: (number | null)[], rank: Rank): number | null => {
    const nums = values.filter((v): v is number => v !== null && Number.isFinite(v));
    if (nums.length < 2 || new Set(nums).size < 2) return null;
    const target = rank.better === "low" ? Math.min(...nums) : Math.max(...nums);
    return values.indexOf(target);
  };
  const rows = data.rows.filter((r) => r.field !== "currency" && (!onlyDiff || r.differs));
  const ppm2 = numbers(data.price_per_m2);
  const ppm2Best = data.same_currency ? bestIndex(ppm2, { better: "low" }) : null;
  const query = (all: boolean) =>
    `/compare?ids=${encodeURIComponent(ids.join(","))}${all ? "&all=1" : ""}`;
  const grid = { gridTemplateColumns: `minmax(9rem,13rem) repeat(${n}, minmax(13rem, 1fr))` };

  return (
    <div className="page flex flex-col gap-6 pb-10">
      <PageHeader
        title={c.title}
        lede={c.lede}
        actions={
          <nav className="seg" aria-label={c.title}>
            <Link href={query(false)} aria-current={onlyDiff ? "page" : undefined}>
              {c.onlyDifferences}
            </Link>
            <Link href={query(true)} aria-current={!onlyDiff ? "page" : undefined}>
              {c.allDetails}
            </Link>
          </nav>
        }
      />
      {!data.same_currency && <Alert tone="info">{c.differentCurrencies}</Alert>}

      {/* One sheet: properties as columns, details as rows. The label column
          stays put while the properties scroll sideways on small screens. */}
      <div className="quiet-scroll -mx-[var(--gutter)] overflow-x-auto px-[var(--gutter)]">
        <div className="grid min-w-max" style={grid} role="table" aria-label={c.title}>
          <div role="row" className="contents">
            <div role="columnheader" className="sticky start-0 z-10 bg-canvas" />
            {data.items.map((p) => {
              const photo = cover(p);
              return (
                <div key={p.id} role="columnheader" className="flex flex-col gap-3 px-3 pb-5">
                  <Link
                    href={`/properties/${p.id}`}
                    className="group relative block aspect-[4/3] overflow-hidden rounded-[var(--radius-media)] bg-fill"
                  >
                    {photo ? (
                      <SafeImage
                        src={photo.thumbnail_url ?? photo.url}
                        alt=""
                        fallbackLabel="—"
                        className="photo size-full object-cover transition-transform duration-[var(--duration-slow)] group-hover:scale-[1.03]"
                      />
                    ) : (
                      <span className="grid size-full place-items-center text-ink-3">
                        <Icon name="home" className="size-6" />
                      </span>
                    )}
                    {p.is_demo && (
                      <span className="absolute start-0 bottom-0 rounded-se-[var(--radius-tag)] bg-gold-500 px-2 py-0.5 text-[11px] font-semibold text-[#1d1405]">
                        {dict.listing.demo}
                      </span>
                    )}
                  </Link>
                  <div className="flex flex-col gap-1">
                    <p className="kpi text-xl text-ink">
                      {p.price_on_request
                        ? dict.listing.priceOnRequest
                        : formatPrice(p.price_amount, p.currency, locale)}
                    </p>
                    <Link
                      href={`/properties/${p.id}`}
                      className="line-clamp-2 text-[15px] leading-snug font-medium text-ink hover:text-accent"
                    >
                      {title(p)}
                    </Link>
                    <p className="meta flex items-center gap-1">
                      <Icon name="pin" className="size-3.5 shrink-0 text-spatial" />
                      <span className="truncate">
                        {placeName(p.district, locale) || placeName(p.city, locale)}
                      </span>
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {rows.length === 0 && (
            <p className="col-span-full border-t border-hairline py-6 text-ink-2">
              {c.sameEverywhere}
            </p>
          )}

          {[
            ...rows.map((row) => ({
              key: row.field,
              label: fieldLabel[row.field] ?? row.field,
              row,
            })),
            { key: "price_per_m2", label: c.pricePerM2, row: null },
          ].map(({ key, label: rowLabel, row }) => {
            const raw = row ? row.values : data.price_per_m2;
            const rank = row ? RANK[row.field] : { better: "low" as const, money: true };
            const comparable = rank && (!rank.money || data.same_currency);
            const nums = comparable ? numbers(raw) : null;
            const best = row
              ? rank && comparable && nums
                ? bestIndex(nums, rank)
                : null
              : ppm2Best;
            const max = nums ? Math.max(...nums.filter((v): v is number => v !== null), 0) : 0;
            return (
              <div key={key} role="row" className="group contents">
                <div
                  role="rowheader"
                  className="sticky start-0 z-10 flex items-center border-t border-hairline bg-canvas py-4 pe-4 text-[14px] text-ink-2"
                >
                  {rowLabel}
                </div>
                {raw.map((v, i) => {
                  const p = data.items[i] as Property;
                  const text = row
                    ? show(row.field, v, p)
                    : v
                      ? (formatPrice(v, p.currency, locale) ?? c.notProvided)
                      : c.notProvided;
                  const num = nums?.[i] ?? null;
                  return (
                    <div
                      key={p.id}
                      role="cell"
                      className={`flex flex-col justify-center gap-1.5 border-t border-hairline px-3 py-4 ${best === i ? "bg-accent-tint/40" : ""}`}
                    >
                      <span
                        className={`tabular text-[15px] ${v === null || v === "" ? "text-ink-3" : "text-ink"} ${best === i ? "font-semibold" : ""}`}
                      >
                        {text}
                      </span>
                      {num !== null && max > 0 && (
                        <span
                          aria-hidden
                          className="h-1 w-full overflow-hidden rounded-full bg-fill"
                        >
                          <span
                            className={`block h-full rounded-full ${best === i ? "bg-accent-fill" : "bg-ink-3/40"}`}
                            style={{ width: `${Math.max(4, (num / max) * 100)}%` }}
                          />
                        </span>
                      )}
                      {best === i && (
                        <span className="caption flex items-center gap-1 text-accent">
                          <Icon name="check" className="size-3.5" strokeWidth={2.2} />
                          {key === "price_per_m2" ? c.cheapest : c.best}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {data.amenities_common.length > 0 && (
        <p className="text-[15px] text-ink-2">
          <span className="font-medium text-ink">{c.commonAmenities}:</span>{" "}
          {data.amenities_common.map((a) => label(amenities, a)).join("، ")}
        </p>
      )}

      {analysis && (
        <section
          className="flex flex-col gap-4 rounded-[var(--radius-card)] bg-surface p-6 shadow-[inset_0_0_0_1px_var(--hairline)] md:p-8"
          data-testid="ai-compare"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="title flex items-center gap-2 text-ink">
              <Icon name="sparkle" className="size-5 text-accent" />
              {dict.ai.compareAnalysis}
            </h2>
            <ProviderBadge dict={dict} provider={analysis.provider} model={analysis.model} />
          </div>
          {!analysis.result.prices_comparable && (
            <p className="text-ink-2">{dict.ai.notComparable}</p>
          )}
          <ul className="grid gap-3 md:grid-cols-2">
            {analysis.result.properties.map((row) => {
              const p = data.items.find((i) => i.id === row.id);
              if (!p) return null;
              const tags = [
                analysis.result.highlights.lowest_price_per_m2 === row.id && dict.ai.cheapestPerM2,
                analysis.result.highlights.largest_area === row.id && dict.ai.largest,
                analysis.result.highlights.most_bedrooms === row.id && dict.ai.mostBedrooms,
              ].filter(Boolean);
              return (
                <li
                  key={row.id}
                  className="flex flex-col gap-1.5 rounded-[var(--radius-control)] bg-fill/60 p-4"
                >
                  <p className="line-clamp-1 font-medium text-ink">{title(p)}</p>
                  <p className="tabular text-ink-2">
                    {dict.ai.pricePerM2}:{" "}
                    {row.price_per_m2
                      ? formatPrice(row.price_per_m2, p.currency, locale)
                      : c.notProvided}
                    {row.vs_local_median_percent !== null && (
                      <span className="caption ms-2">
                        ({dict.ai.vsCityMedian}: {row.vs_local_median_percent > 0 ? "+" : ""}
                        {row.vs_local_median_percent}%)
                      </span>
                    )}
                  </p>
                  {tags.length > 0 && (
                    <p className="flex flex-wrap gap-1.5">
                      {tags.map((t) => (
                        <span
                          key={String(t)}
                          className="rounded-[var(--radius-tag)] bg-accent-tint px-2 py-0.5 text-[12px] font-medium text-accent"
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
          <p className="caption">{analysis.methodology}</p>
        </section>
      )}
    </div>
  );
}
