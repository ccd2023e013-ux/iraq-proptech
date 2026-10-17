import { PageHeader } from "@/components/ui/PageHeader";
import type { Metadata } from "next";
import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { TrustBadge, type TrustKind } from "@/components/ui/TrustBadge";
import {
  fill,
  methodText,
  num,
  provenanceLine,
  renderMarketStatement,
} from "@/features/market/statements";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { formatCompactPrice, formatPrice } from "@/lib/format";
import type { MarketCity, MarketKind, MarketReport, MarketStatement } from "@/types/market";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.market.title, description: dict.market.subtitle };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const KIND_BADGE: Record<MarketKind, TrustKind> = {
  FACT: "fact",
  OBSERVED: "observed",
  ESTIMATE: "estimate",
  AI_INTERPRETATION: "ai",
  SIMULATION: "simulation",
};
const SECTION_ORDER = ["supply", "prices", "dynamics", "demand", "quality", "areas"] as const;

type RawParams = Record<string, string | string[] | undefined>;

function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function MarketPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const t = dict.market;
  const params = await searchParams;
  const city = one(params.city_id);
  const district = one(params.district_id);
  const includeDemo = one(params.demo) !== "0";

  const query = new URLSearchParams({ language: locale, include_demo: String(includeDemo) });
  if (district && UUID.test(district)) query.set("district_id", district);
  else if (city && UUID.test(city)) query.set("city_id", city);

  const [cities, report] = await Promise.all([
    serverApiFetch<MarketCity[]>("/api/v1/market/cities").catch(() => [] as MarketCity[]),
    serverApiFetch<MarketReport>(`/api/v1/market/report?${query}`).catch(() => null),
  ]);
  const name = (p: { name_ar: string; name_en: string | null }) =>
    (locale === "en" && p.name_en) || p.name_ar;
  const scopeName = report
    ? report.scope.level === "iraq"
      ? t.scopeIraq
      : name(report.scope)
    : t.scopeIraq;

  const ai = report?.statements.find((s) => s.kind === "AI_INTERPRETATION");
  const bySection = new Map<string, { s: MarketStatement; text: string }[]>();
  for (const s of report?.statements ?? []) {
    if (s.kind === "AI_INTERPRETATION") continue;
    const text = renderMarketStatement(s, dict, locale);
    if (!text) continue;
    bySection.set(s.section, [...(bySection.get(s.section) ?? []), { s, text }]);
  }
  const empty = report?.provenance.sample_listings === 0;
  const basisCurrency = report?.areas_basis?.currency ?? "IQD";
  const bars = (report?.areas ?? []).filter(
    (a) => a.median_price_per_m2 && a.currency === basisCurrency,
  );
  const maxBar = Math.max(1, ...bars.map((a) => Number(a.median_price_per_m2)));
  // Range bars share one scale per purpose + currency (sale vs rent, IQD vs USD
  // are never drawn against each other).
  const rangeMax = new Map<string, number>();
  for (const seg of report?.segments ?? []) {
    if (!seg.p75_price) continue;
    const key = `${seg.purpose}-${seg.currency}`;
    rangeMax.set(key, Math.max(rangeMax.get(key) ?? 0, Number(seg.p75_price)));
  }
  const p = report?.provenance;
  const date = (d: string | null) =>
    d
      ? new Date(d).toLocaleDateString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-GB", {
          day: "numeric",
          month: "short",
          year: "numeric",
        })
      : "—";
  const areaHref = (id: string, level: string) => {
    const q = new URLSearchParams(level === "district" ? { district_id: id } : { city_id: id });
    // keep the parent city in the URL so the area picker still shows it
    if (level === "district" && report?.scope.level === "city" && report.scope.id)
      q.set("city_id", report.scope.id);
    if (!includeDemo) q.set("demo", "0");
    return `/market?${q}`;
  };

  // Segments grouped by what can share a scale: one purpose, one currency.
  const groups = new Map<string, NonNullable<typeof report>["segments"]>();
  for (const seg of report?.segments ?? []) {
    const key = `${seg.purpose}-${seg.currency}`;
    groups.set(key, [...(groups.get(key) ?? []), seg]);
  }
  const purposeName = (code: string) =>
    (dict.listing.purposes as Record<string, string>)[code] ?? code;
  const sortedBars = [...bars].sort(
    (a, b) => Number(b.median_price_per_m2) - Number(a.median_price_per_m2),
  );

  return (
    <div className="page flex flex-col gap-14 pb-10">
      <header className="flex flex-col gap-6">
        <PageHeader
          title={
            <>
              <span className="mb-2 block font-sans text-base font-medium tracking-normal text-ink-2">
                {t.title}
              </span>
              <span className="place block">{scopeName}</span>
            </>
          }
          lede={t.subtitle}
          actions={
            <form
              method="get"
              action="/market"
              className="flex flex-wrap items-center gap-2"
              data-testid="market-controls"
            >
              <label className="flex flex-col gap-1">
                <span className="sr-only">{t.area}</span>
                <select
                  name="city_id"
                  defaultValue={city && UUID.test(city) ? city : ""}
                  className="field min-w-52"
                >
                  <option value="">{t.allIraq}</option>
                  {cities.map((c) => (
                    <option key={c.city_id} value={c.city_id}>
                      {name(c)} ({num(c.listings, locale)})
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex h-12 items-center gap-2 px-1 text-sm text-ink-2">
                <input
                  type="checkbox"
                  name="demo"
                  value="1"
                  defaultChecked={includeDemo}
                  className="size-4"
                />
                {/* Sent after the checkbox: when it is ticked, "1" comes first and wins. */}
                <input type="hidden" name="demo" value="0" />
                {t.includeDemo}
              </label>
              <button type="submit" className="btn btn-primary">
                {t.show}
              </button>
            </form>
          }
        />
        {/* How to read: every number on this page carries one of these labels. */}
        <details className="group max-w-3xl border-y border-hairline py-3">
          <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-ink [&::-webkit-details-marker]:hidden">
            <Icon name="info" className="size-4 text-ink-3" />
            {t.readGuide}
            <Icon
              name="chevron-down"
              className="ms-auto size-4 transition-transform group-open:rotate-180"
            />
          </summary>
          <p className="mt-3 text-sm leading-relaxed text-ink-2">{t.honesty}</p>
          <p className="mt-3 flex flex-wrap gap-2">
            {(Object.keys(KIND_BADGE) as MarketKind[]).map((k) => (
              <TrustBadge key={k} kind={KIND_BADGE[k]}>
                {t.kinds[k]}
              </TrustBadge>
            ))}
          </p>
        </details>
      </header>

      {!report && <p className="text-ink-2">{dict.errors.UNKNOWN}</p>}
      {report && empty && (
        <p className="text-ink-2" data-testid="market-empty">
          {t.empty}
        </p>
      )}

      {report && !empty && p && (
        <>
          {/* The reading in one paragraph (labelled AI), beside the facts it rests on. */}
          <section className="grid gap-8 lg:grid-cols-12 lg:gap-12">
            {ai?.text ? (
              <div className="flex flex-col gap-3 lg:col-span-7" data-testid="market-ai">
                <h2 className="sr-only">{t.sections.interpretation}</h2>
                <div className="flex flex-wrap items-center gap-2">
                  <TrustBadge kind="ai">{t.kinds.AI_INTERPRETATION}</TrustBadge>
                  {ai.demo && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
                </div>
                <p className="font-display text-[1.375rem] leading-[1.55] text-ink md:text-2xl">
                  {ai.text}
                </p>
                <p className="caption" title={methodText(ai, dict)}>
                  {provenanceLine(ai, dict, locale)}
                </p>
              </div>
            ) : (
              <div className="lg:col-span-7" />
            )}
            <dl className="grid grid-cols-2 gap-px self-start overflow-hidden border-y border-hairline-strong bg-hairline lg:col-span-5">
              {[
                [t.headline.listings, num(p.sample_listings, locale)],
                [t.headline.period, `${date(p.observation_from)} – ${date(p.observation_to)}`],
                [t.headline.demoShare, `${num(Math.round(p.demo_share * 100), locale)}%`],
                [t.headline.confidence, t.confidence[p.confidence]],
              ].map(([k, val], i) => (
                <div key={k} className="flex flex-col gap-1 bg-canvas py-4 odd:pe-4 even:ps-4">
                  <dt className="meta">{k}</dt>
                  <dd
                    className={`text-ink ${i === 0 ? "kpi text-4xl" : "text-[15px] font-medium"}`}
                  >
                    {val}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          {groups.size > 0 && (
            <section aria-labelledby="market-segments-title" className="flex flex-col gap-6">
              <div className="flex flex-col gap-1">
                <h2 id="market-segments-title" className="display-md text-ink">
                  {t.segmentsTitle}
                </h2>
                <p className="meta max-w-3xl">
                  {t.chartRange} {t.segmentsNote}
                </p>
              </div>
              <div className="grid gap-10 lg:grid-cols-2">
                {[...groups.entries()].map(([key, segs]) => (
                  <RangeChart
                    key={key}
                    title={`${purposeName(segs[0]!.purpose)} · ${segs[0]!.currency}`}
                    rows={segs.map((seg) => ({
                      label: locale === "ar" ? seg.type_ar : seg.type_en,
                      listings: seg.listings,
                      low: seg.p25_price ? Number(seg.p25_price) : null,
                      high: seg.p75_price ? Number(seg.p75_price) : null,
                      mid: seg.median_price ? Number(seg.median_price) : null,
                    }))}
                    max={rangeMax.get(key) ?? 0}
                    format={(v) => formatCompactPrice(v, segs[0]!.currency, locale) ?? ""}
                    listingsLabel={(n) => fill(t.sample, { n: num(n, locale) })}
                    notEnough={t.notEnough}
                  />
                ))}
              </div>
              <details className="group">
                <summary className="chip w-fit cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                  {t.showTable}
                  <Icon name="chevron-down" className="size-3.5 group-open:rotate-180" />
                </summary>
                <div className="quiet-scroll mt-4 overflow-x-auto">
                  <table
                    className="w-full min-w-[40rem] text-start text-sm"
                    data-testid="market-segments"
                  >
                    <thead className="text-ink-3">
                      <tr className="border-b border-hairline">
                        <th className="py-2 pe-4 text-start font-medium">{t.cols.segment}</th>
                        <th className="py-2 pe-4 text-end font-medium">{t.cols.listings}</th>
                        <th className="py-2 pe-4 text-end font-medium">{t.cols.median}</th>
                        <th className="py-2 pe-4 text-end font-medium">{t.cols.range}</th>
                        <th className="py-2 text-end font-medium">{t.cols.perM2}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-hairline">
                      {report.segments.map((seg) => (
                        <tr key={`${seg.property_type_code}-${seg.purpose}-${seg.currency}`}>
                          <td className="py-3 pe-4 text-ink">
                            {locale === "ar" ? seg.type_ar : seg.type_en}{" "}
                            <span className="text-ink-3">
                              {purposeName(seg.purpose)} · {seg.currency}
                            </span>
                          </td>
                          <td className="py-3 pe-4 text-end tabular text-ink-2">
                            {num(seg.listings, locale)}
                          </td>
                          <td className="py-3 pe-4 text-end tabular text-ink">
                            {seg.median_price
                              ? formatPrice(seg.median_price, seg.currency, locale)
                              : t.notEnough}
                          </td>
                          <td className="py-3 pe-4 text-end tabular text-ink-2">
                            {seg.p25_price && seg.p75_price
                              ? `${formatPrice(seg.p25_price, seg.currency, locale)} – ${formatPrice(seg.p75_price, seg.currency, locale)}`
                              : "—"}
                          </td>
                          <td className="py-3 text-end tabular text-ink-2">
                            {seg.median_price_per_m2
                              ? formatPrice(seg.median_price_per_m2, seg.currency, locale)
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </section>
          )}

          {report.areas.length > 0 && (
            <section aria-labelledby="market-areas" className="flex flex-col gap-5">
              <div className="flex flex-col gap-1">
                <h2 id="market-areas" className="display-md text-ink">
                  {t.areasTitle}
                </h2>
                <p className="meta max-w-3xl">
                  {t.chartAreas}{" "}
                  {report.areas_basis &&
                    fill(t.areasBasis, {
                      type:
                        locale === "ar" ? report.areas_basis.type_ar : report.areas_basis.type_en,
                      purpose: purposeName(report.areas_basis.purpose),
                      currency: report.areas_basis.currency,
                    })}
                </p>
              </div>
              <ul className="flex flex-col" data-testid="market-areas">
                {[...sortedBars, ...report.areas.filter((a) => !sortedBars.includes(a))].map(
                  (a) => {
                    const value =
                      a.median_price_per_m2 && a.currency === basisCurrency
                        ? Number(a.median_price_per_m2)
                        : null;
                    const shown = value
                      ? formatPrice(a.median_price_per_m2, basisCurrency, locale)
                      : null;
                    return (
                      <li
                        key={a.id}
                        className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)] items-center gap-4 border-t border-hairline py-3 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]"
                      >
                        <Link
                          href={areaHref(a.id, a.level)}
                          className="flex min-w-0 flex-col text-ink hover:text-accent"
                          aria-label={fill(t.openArea, { name: name(a) })}
                        >
                          <span className="truncate font-medium">{name(a)}</span>
                          <span className="caption tabular">
                            {fill(t.areaListings, { n: num(a.active_listings, locale) })}
                          </span>
                        </Link>
                        {value && shown ? (
                          <div
                            className="flex min-w-0 items-center gap-3"
                            title={`${name(a)}: ${shown} · ${fill(t.sample, { n: num(a.sample, locale) })}`}
                          >
                            <span
                              aria-hidden
                              className="h-2.5 shrink-0 rounded-e-[4px] bg-spatial-fill"
                              style={{ width: `${Math.max(2, (value / maxBar) * 62)}%` }}
                            />
                            <span className="truncate text-sm text-ink tabular">{shown}</span>
                          </div>
                        ) : (
                          <span className="caption">
                            {t.notEnough} ({fill(t.sample, { n: num(a.sample, locale) })})
                          </span>
                        )}
                      </li>
                    );
                  },
                )}
              </ul>
            </section>
          )}

          <section aria-labelledby="market-statements" className="flex flex-col gap-6">
            <h2 id="market-statements" className="display-md text-ink">
              {t.evidenceTitle}
            </h2>
            <div className="grid gap-x-10 gap-y-10 md:grid-cols-2 xl:grid-cols-3">
              {SECTION_ORDER.filter((k) => bySection.has(k)).map((section) => (
                <div key={section} className="flex flex-col gap-3">
                  <h3 className="label">{t.sections[section]}</h3>
                  <ul className="flex flex-col divide-y divide-hairline border-y border-hairline">
                    {(bySection.get(section) ?? []).map(({ s, text }) => (
                      <li
                        key={`${s.key}-${text}`}
                        className="flex flex-col gap-1.5 py-3.5"
                        data-testid="market-statement"
                        data-kind={s.kind}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <TrustBadge kind={KIND_BADGE[s.kind]}>{t.kinds[s.kind]}</TrustBadge>
                          {s.demo && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
                          {s.sample ? (
                            <span className="caption tabular">
                              {fill(t.sample, { n: num(s.sample, locale) })}
                            </span>
                          ) : null}
                        </div>
                        <p className="text-[15px] leading-relaxed text-ink">{text}</p>
                        <p
                          className="caption"
                          title={methodText(s, dict)}
                          data-testid="market-statement-provenance"
                        >
                          {provenanceLine(s, dict, locale)}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {report && report.unavailable.length > 0 && (
        <section
          aria-labelledby="market-gaps"
          className="flex flex-col gap-4"
          data-testid="market-unavailable"
        >
          <h2 id="market-gaps" className="display-md text-ink">
            {t.unavailableTitle}
          </h2>
          <ul className="grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
            {report.unavailable.map((u) => (
              <li
                key={u.metric}
                className="flex flex-col gap-1 border-t border-hairline py-3 text-sm"
              >
                <span className="font-medium text-ink">
                  {(t.metrics as Record<string, string>)[u.metric] ?? u.metric}
                </span>
                <span className="text-ink-2">
                  {fill((t.reasons as Record<string, string>)[u.reason] ?? u.reason, {
                    months: num(u.detail.months_with_enough_listings ?? 0, locale),
                    closed: num(u.detail.closed_listings ?? 0, locale),
                    days: num(u.detail.days_recorded ?? 0, locale),
                  })}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {p && (
        <section
          aria-labelledby="market-provenance"
          className="flex flex-col gap-5 border-t border-hairline-strong pt-6"
          data-testid="market-provenance"
        >
          <h2 id="market-provenance" className="title text-ink">
            {t.provenanceTitle}
          </h2>
          <dl className="grid gap-x-8 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {[
              [t.prov.source, t.sourceText],
              [t.prov.coverage, scopeName],
              [t.prov.period, `${date(p.observation_from)} – ${date(p.observation_to)}`],
              [t.prov.sample, fill(t.sample, { n: num(p.sample_listings, locale) })],
              [t.prov.demo, `${num(Math.round(p.demo_share * 100), locale)}%`],
              [
                t.prov.confidence,
                `${t.confidence[p.confidence]} (${p.confidence_reasons
                  .map((r) => (t.confidenceReasons as Record<string, string>)[r] ?? r)
                  .join(locale === "ar" ? "، " : ", ")})`,
              ],
              [t.prov.updated, date(p.last_update)],
            ].map(([k, v]) => (
              <div key={k} className="flex flex-col gap-0.5">
                <dt className="meta">{k}</dt>
                <dd className="text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="flex flex-col gap-1 text-sm">
            <p className="meta">{t.prov.methodology}</p>
            <ul className="list-disc ps-5 text-ink-2">
              {t.methodLines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          {p.includes_demo && (
            <p className="caption flex items-center gap-2">
              <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
              {dict.footer.demoNotice}
            </p>
          )}
        </section>
      )}
    </div>
  );
}

/**
 * Asking-price ranges on one shared scale (one purpose, one currency): for each
 * property type the middle half (P25–P75) as a bar and the median as a dot,
 * with the median written at the end. Rows without enough data say so.
 */
function RangeChart({
  title,
  rows,
  max,
  format,
  listingsLabel,
  notEnough,
}: {
  title: string;
  rows: {
    label: string;
    listings: number;
    low: number | null;
    high: number | null;
    mid: number | null;
  }[];
  max: number;
  format: (v: number) => string;
  listingsLabel: (n: number) => string;
  notEnough: string;
}) {
  const scale = max > 0 ? max * 1.08 : 1;
  const pct = (v: number) => `${Math.min(100, Math.max(0, (v / scale) * 100))}%`;
  const ticks = max > 0 ? [0, scale / 2, scale] : [];
  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="label">{title}</figcaption>
      <ul className="flex flex-col">
        {rows.map((r) => (
          <li
            key={r.label}
            className="grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)] items-center gap-4 border-t border-hairline py-3 sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)]"
          >
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-[15px] text-ink">{r.label}</span>
              <span className="caption tabular">{listingsLabel(r.listings)}</span>
            </span>
            {r.low !== null && r.high !== null && max > 0 ? (
              <span
                className="relative h-10"
                title={`${r.label}: ${format(r.low)} – ${format(r.high)}${r.mid !== null ? ` · ${format(r.mid)}` : ""}`}
              >
                <span aria-hidden className="absolute inset-x-0 top-[70%] h-px bg-hairline" />
                <span
                  aria-hidden
                  className="absolute top-[70%] h-2.5 -translate-y-1/2 rounded-[3px] bg-ink/18"
                  style={{
                    insetInlineStart: pct(r.low),
                    width: `calc(${pct(r.high)} - ${pct(r.low)})`,
                  }}
                />
                {r.mid !== null && (
                  <span
                    aria-hidden
                    className="absolute top-[70%] size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink shadow-[0_0_0_2px_var(--canvas)] rtl:translate-x-1/2"
                    style={{ insetInlineStart: pct(r.mid) }}
                  />
                )}
                {r.mid !== null && (
                  <span
                    className="absolute top-0 text-[12.5px] leading-4 font-semibold whitespace-nowrap text-ink tabular"
                    style={{ insetInlineStart: `min(${pct(r.mid)}, calc(100% - 4.5rem))` }}
                  >
                    {format(r.mid)}
                  </span>
                )}
              </span>
            ) : (
              <span className="caption">{notEnough}</span>
            )}
          </li>
        ))}
      </ul>
      {ticks.length > 0 && (
        <div className="grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)] gap-4 sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)]">
          <span />
          <span className="caption relative h-4 tabular">
            {ticks.map((v, i) => (
              <span
                key={v}
                className={`absolute whitespace-nowrap ${i === 1 ? "-translate-x-1/2 max-sm:hidden rtl:translate-x-1/2" : ""}`}
                style={{
                  insetInlineStart: i === ticks.length - 1 ? undefined : pct(v),
                  insetInlineEnd: i === ticks.length - 1 ? 0 : undefined,
                }}
              >
                {format(v)}
              </span>
            ))}
          </span>
        </div>
      )}
    </figure>
  );
}
