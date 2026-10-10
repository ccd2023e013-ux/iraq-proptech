import type { Metadata } from "next";
import Link from "next/link";

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
import { formatPrice } from "@/lib/format";
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

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-10 sm:px-6">
      <header className="flex flex-col gap-4">
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          {t.title}
          <span className="block text-ink-3">{scopeName}</span>
        </h1>
        <p className="max-w-2xl text-lg text-ink-2">{t.subtitle}</p>
        <p className="max-w-2xl rounded-[var(--radius-control)] bg-fill px-4 py-3 text-sm text-ink-2">
          {t.honesty}
        </p>
        <form
          method="get"
          action="/market"
          className="flex flex-wrap items-end gap-3"
          data-testid="market-controls"
        >
          <label className="flex flex-col gap-1 text-sm text-ink-2">
            {t.area}
            <select
              name="city_id"
              defaultValue={city && UUID.test(city) ? city : ""}
              className="h-11 min-w-56 rounded-[var(--radius-control)] border border-hairline bg-surface px-3 text-ink"
            >
              <option value="">{t.allIraq}</option>
              {cities.map((c) => (
                <option key={c.city_id} value={c.city_id}>
                  {name(c)} ({num(c.listings, locale)})
                </option>
              ))}
            </select>
          </label>
          <label className="flex h-11 items-center gap-2 text-sm text-ink-2">
            <input
              type="checkbox"
              name="demo"
              value="1"
              defaultChecked={includeDemo}
              className="size-4 accent-[var(--accent-fill)]"
            />
            {/* Sent after the checkbox: when it is ticked, "1" comes first and wins. */}
            <input type="hidden" name="demo" value="0" />
            {t.includeDemo}
          </label>
          <button
            type="submit"
            className="h-11 rounded-[var(--radius-control)] bg-accent-fill px-5 text-sm font-semibold text-on-accent"
          >
            {t.show}
          </button>
        </form>
      </header>

      {!report && <p className="text-ink-2">{dict.errors.UNKNOWN}</p>}
      {report && empty && (
        <p className="text-ink-2" data-testid="market-empty">
          {t.empty}
        </p>
      )}

      {report && !empty && (
        <>
          {ai?.text && (
            <section
              aria-labelledby="market-ai"
              className="flex flex-col gap-3 border-s-4 border-accent-fill ps-5"
              data-testid="market-ai"
            >
              <div className="flex flex-wrap items-center gap-2">
                <h2 id="market-ai" className="sr-only">
                  {t.sections.interpretation}
                </h2>
                <TrustBadge kind="ai">{t.kinds.AI_INTERPRETATION}</TrustBadge>
                {ai.demo && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
              </div>
              <p className="max-w-3xl text-lg text-ink">{ai.text}</p>
              <p className="text-xs text-ink-3" title={methodText(ai, dict)}>
                {provenanceLine(ai, dict, locale)}
              </p>
            </section>
          )}

          <section aria-labelledby="market-statements" className="flex flex-col gap-6">
            <h2 id="market-statements" className="sr-only">
              {t.title}
            </h2>
            <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
              {SECTION_ORDER.filter((k) => bySection.has(k)).map((section) => (
                <div key={section} className="flex flex-col gap-3">
                  <h3 className="font-display text-xl font-semibold text-ink">
                    {t.sections[section]}
                  </h3>
                  <ul className="flex flex-col divide-y divide-hairline border-y border-hairline">
                    {(bySection.get(section) ?? []).map(({ s, text }) => (
                      <li
                        key={`${s.key}-${text}`}
                        className="flex flex-col gap-1.5 py-3"
                        data-testid="market-statement"
                        data-kind={s.kind}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <TrustBadge kind={KIND_BADGE[s.kind]}>{t.kinds[s.kind]}</TrustBadge>
                          {s.demo && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
                          {s.sample ? (
                            <span className="text-xs text-ink-3 tabular">
                              {fill(t.sample, { n: num(s.sample, locale) })}
                            </span>
                          ) : null}
                        </div>
                        <p className="text-ink">{text}</p>
                        <p
                          className="text-xs text-ink-3"
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

          {report.segments.length > 0 && (
            <section aria-labelledby="market-segments" className="flex flex-col gap-3">
              <h2
                id="market-segments"
                className="font-display text-2xl font-semibold tracking-tight text-ink"
              >
                {t.segmentsTitle}
              </h2>
              <p className="text-sm text-ink-3">{t.segmentsNote}</p>
              <div className="overflow-x-auto">
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
                    {report.segments.map((s) => (
                      <tr key={`${s.property_type_code}-${s.purpose}-${s.currency}`}>
                        <td className="py-3 pe-4 text-ink">
                          {locale === "ar" ? s.type_ar : s.type_en}{" "}
                          <span className="text-ink-3">
                            {(dict.listing.purposes as Record<string, string>)[s.purpose] ??
                              s.purpose}{" "}
                            · {s.currency}
                          </span>
                        </td>
                        <td className="py-3 pe-4 text-end tabular text-ink-2">
                          {num(s.listings, locale)}
                        </td>
                        <td className="py-3 pe-4 text-end tabular text-ink">
                          {s.median_price ? (
                            formatPrice(s.median_price, s.currency, locale)
                          ) : (
                            <span className="text-ink-3">{t.notEnough}</span>
                          )}
                        </td>
                        <td className="py-3 pe-4 text-end tabular text-ink-2">
                          {s.p25_price && s.p75_price
                            ? `${formatPrice(s.p25_price, s.currency, locale)} – ${formatPrice(s.p75_price, s.currency, locale)}`
                            : "—"}
                          {s.p25_price && s.p75_price && (
                            <RangeBar
                              low={Number(s.p25_price)}
                              high={Number(s.p75_price)}
                              mid={s.median_price ? Number(s.median_price) : null}
                              max={rangeMax.get(`${s.purpose}-${s.currency}`) ?? 0}
                            />
                          )}
                        </td>
                        <td className="py-3 text-end tabular text-ink-2">
                          {s.median_price_per_m2
                            ? formatPrice(s.median_price_per_m2, s.currency, locale)
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {report.areas.length > 0 && (
            <section aria-labelledby="market-areas" className="flex flex-col gap-3">
              <h2
                id="market-areas"
                className="font-display text-2xl font-semibold tracking-tight text-ink"
              >
                {t.areasTitle}
              </h2>
              {report.areas_basis && (
                <p className="text-sm text-ink-3">
                  {fill(t.areasBasis, {
                    type: locale === "ar" ? report.areas_basis.type_ar : report.areas_basis.type_en,
                    purpose:
                      (dict.listing.purposes as Record<string, string>)[
                        report.areas_basis.purpose
                      ] ?? report.areas_basis.purpose,
                    currency: report.areas_basis.currency,
                  })}
                </p>
              )}
              <ul
                className="flex flex-col divide-y divide-hairline border-y border-hairline"
                data-testid="market-areas"
              >
                {report.areas.map((a) => {
                  const value =
                    a.median_price_per_m2 && a.currency === basisCurrency
                      ? Number(a.median_price_per_m2)
                      : null;
                  const label = value
                    ? formatPrice(a.median_price_per_m2, basisCurrency, locale)
                    : null;
                  return (
                    <li
                      key={a.id}
                      className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)] items-center gap-4 py-3 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]"
                    >
                      <Link
                        href={areaHref(a.id, a.level)}
                        className="flex flex-col text-ink hover:text-accent"
                        aria-label={fill(t.openArea, { name: name(a) })}
                      >
                        <span className="truncate font-medium">{name(a)}</span>
                        <span className="text-xs text-ink-3 tabular">
                          {fill(t.areaListings, { n: num(a.active_listings, locale) })}
                        </span>
                      </Link>
                      {value && label ? (
                        <div
                          className="flex items-center gap-3"
                          title={`${name(a)}: ${label} · ${fill(t.sample, { n: num(a.sample, locale) })}`}
                        >
                          <span
                            className="h-3 rounded-e-[4px] bg-accent-fill"
                            style={{ width: `${Math.max(2, (value / maxBar) * 70)}%` }}
                            aria-hidden
                          />
                          <span className="shrink-0 text-sm text-ink tabular">{label}</span>
                        </div>
                      ) : (
                        <span className="text-sm text-ink-3">
                          {t.notEnough} ({fill(t.sample, { n: num(a.sample, locale) })})
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
        </>
      )}

      {report && report.unavailable.length > 0 && (
        <section
          aria-labelledby="market-gaps"
          className="flex flex-col gap-3"
          data-testid="market-unavailable"
        >
          <h2
            id="market-gaps"
            className="font-display text-2xl font-semibold tracking-tight text-ink"
          >
            {t.unavailableTitle}
          </h2>
          <ul className="flex flex-col gap-2">
            {report.unavailable.map((u) => (
              <li key={u.metric} className="flex flex-col gap-0.5 text-sm sm:flex-row sm:gap-3">
                <span className="font-medium text-ink sm:w-60 sm:shrink-0">
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
          className="flex flex-col gap-4 rounded-[var(--radius-card)] bg-surface p-6 ring-1 ring-hairline"
          data-testid="market-provenance"
        >
          <h2 id="market-provenance" className="font-display text-xl font-semibold text-ink">
            {t.provenanceTitle}
          </h2>
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
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
                <dt className="text-ink-3">{k}</dt>
                <dd className="text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="flex flex-col gap-1 text-sm">
            <p className="text-ink-3">{t.prov.methodology}</p>
            <ul className="list-disc ps-5 text-ink-2">
              {t.methodLines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          {p.includes_demo && (
            <p className="flex items-center gap-2 text-xs text-ink-3">
              <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
              {dict.footer.demoNotice}
            </p>
          )}
        </section>
      )}
    </div>
  );
}

/** The middle half of asking prices (P25–P75) with the median tick, on a shared scale. */
function RangeBar({
  low,
  high,
  mid,
  max,
}: {
  low: number;
  high: number;
  mid: number | null;
  max: number;
}) {
  if (!(max > 0) || !(high >= low)) return null;
  const pct = (v: number) => `${Math.min(100, Math.max(0, (v / max) * 100))}%`;
  return (
    <span
      aria-hidden
      className="relative ms-auto mt-2 block h-1.5 w-full max-w-[12rem] rounded-full bg-fill"
    >
      <span
        className="absolute inset-y-0 rounded-full bg-spatial-fill/55"
        style={{ insetInlineStart: pct(low), width: `calc(${pct(high)} - ${pct(low)})` }}
      />
      {mid !== null && (
        <span
          className="absolute -inset-y-1 w-0.5 rounded-full bg-ink"
          style={{ insetInlineStart: pct(mid) }}
        />
      )}
    </span>
  );
}
