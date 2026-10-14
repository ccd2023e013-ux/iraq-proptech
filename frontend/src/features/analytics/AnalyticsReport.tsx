import Link from "next/link";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";

import { type AnalyticsOverview, percent } from "./types";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="surface-1 rounded-2xl p-3">
      <dt className="text-xs text-sand-500">{label}</dt>
      <dd className="text-xl font-semibold text-brand-900">{value}</dd>
    </div>
  );
}

/** Accessible CSS bar chart: one column per day, the table below carries the numbers. */
function DailyChart({ data, dict }: { data: AnalyticsOverview; dict: Dictionary }) {
  const t = dict.analytics;
  const max = Math.max(1, ...data.series.map((d) => d.views));
  return (
    <section className="surface-1 rounded-2xl p-4">
      <h2 className="mb-3 font-semibold">{t.perDay}</h2>
      <div className="flex h-32 items-end gap-px" aria-hidden="true" dir="ltr">
        {data.series.map((d) => (
          <div
            key={d.day}
            title={`${d.day}: ${d.views} ${t.views} · ${d.inquiries} ${t.inquiries}`}
            className="relative flex-1 rounded-t bg-brand-200"
            style={{ height: `${(d.views / max) * 100}%`, minHeight: d.views ? 2 : 0 }}
          >
            {d.inquiries > 0 && (
              <span className="absolute inset-x-0 top-0 h-1 rounded-t bg-amber-500" />
            )}
          </div>
        ))}
      </div>
      <p className="mt-1 flex justify-between text-xs text-sand-500" dir="ltr">
        <span>{data.date_from}</span>
        <span>{data.date_to}</span>
      </p>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-accent">{t.perDay}</summary>
        <table className="mt-2 w-full text-xs">
          <thead>
            <tr className="text-sand-500">
              <th className="text-start">—</th>
              <th className="text-start">{t.views}</th>
              <th className="text-start">{t.inquiries}</th>
              <th className="text-start">{t.leads}</th>
            </tr>
          </thead>
          <tbody>
            {data.series
              .filter((d) => d.views || d.inquiries || d.leads)
              .map((d) => (
                <tr key={d.day}>
                  <td dir="ltr" className="text-start">
                    {d.day}
                  </td>
                  <td>{d.views}</td>
                  <td>{d.inquiries}</td>
                  <td>{d.leads}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}

function Bars({ title, rows }: { title: string; rows: [string, number][] }) {
  const max = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <section className="surface-1 rounded-2xl p-4">
      <h2 className="mb-3 font-semibold">{title}</h2>
      <ul className="flex flex-col gap-2 text-sm">
        {rows.map(([label, n]) => (
          <li key={label} className="grid grid-cols-[8rem_1fr_3rem] items-center gap-2">
            <span className="truncate">{label}</span>
            <span className="h-2 rounded bg-brand-300" style={{ width: `${(n / max) * 100}%` }} />
            <span className="text-end tabular-nums">{n}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function AnalyticsReport({
  data,
  dict,
  locale,
}: {
  data: AnalyticsOverview;
  dict: Dictionary;
  locale: Locale;
}) {
  const t = dict.analytics;
  const s = data.summary;
  const purposes = dict.listing.purposes as Record<string, string>;
  return (
    <div className="flex flex-col gap-6">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label={t.views} value={s.views} />
        <Stat label={t.favorites} value={s.favorites} />
        <Stat label={t.inquiries} value={s.inquiries} />
        <Stat label={t.leads} value={s.leads} />
        <Stat label={t.leadsWon} value={s.leads_won} />
        <Stat label={t.listingsActive} value={s.listings_active} />
        <Stat label={t.listingsPublished} value={s.listings_published} />
        <Stat label={t.inquiryRate} value={percent(s.inquiry_rate)} />
        <Stat label={t.winRate} value={percent(s.win_rate)} />
        {data.platform && <Stat label={t.newUsers} value={data.platform.new_users} />}
      </dl>

      <DailyChart data={data} dict={dict} />

      {data.top_listings && (
        <section className="surface-1 rounded-2xl p-4">
          <h2 className="mb-3 font-semibold">{t.topListings}</h2>
          {data.top_listings.length === 0 ? (
            <p className="text-sm text-sand-500">{t.noData}</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-sand-500">
                  <th className="text-start">—</th>
                  <th className="text-start">{t.views}</th>
                  <th className="text-start">{t.favorites}</th>
                  <th className="text-start">{t.inquiries}</th>
                </tr>
              </thead>
              <tbody>
                {data.top_listings.map((row) => (
                  <tr key={row.property_id} className="border-t border-sand-100">
                    <td className="py-1">
                      <Link href={`/properties/${row.property_id}`} className="text-accent">
                        {locale === "en" && row.title_en ? row.title_en : row.title_ar}
                      </Link>
                    </td>
                    <td>{row.views}</td>
                    <td>{row.favorites}</td>
                    <td>{row.inquiries}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {Object.keys(data.leads_by_status).length > 0 && (
        <Bars title={t.leadsByStatus} rows={Object.entries(data.leads_by_status)} />
      )}

      {data.agents && data.agents.length > 0 && (
        <section className="surface-1 rounded-2xl p-4">
          <h2 className="mb-3 font-semibold">{t.agents}</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-sand-500">
                <th className="text-start">{t.agent}</th>
                <th className="text-start">{t.assigned}</th>
                <th className="text-start">{t.won}</th>
                <th className="text-start">{t.activities}</th>
              </tr>
            </thead>
            <tbody>
              {data.agents.map((a) => (
                <tr key={a.user_id} className="border-t border-sand-100">
                  <td className="py-1">{a.name}</td>
                  <td>{a.leads_assigned}</td>
                  <td>{a.leads_won}</td>
                  <td>{a.activities}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {data.platform && (
        <div className="grid gap-4 lg:grid-cols-2">
          <dl className="grid grid-cols-2 gap-3 self-start">
            <Stat label={t.searches} value={data.platform.searches} />
            <Stat label={t.zeroResultRate} value={percent(data.platform.zero_result_rate)} />
          </dl>
          {data.platform.searches_by_governorate.length > 0 && (
            <Bars
              title={t.byGovernorate}
              rows={data.platform.searches_by_governorate.map((g) => [
                locale === "en" ? g.name_en : g.name_ar,
                g.searches,
              ])}
            />
          )}
          {Object.keys(data.platform.searches_by_purpose).length > 0 && (
            <Bars
              title={t.byPurpose}
              rows={Object.entries(data.platform.searches_by_purpose).map(([k, n]) => [
                k === "ANY" ? t.anyPurpose : (purposes[k] ?? k),
                n,
              ])}
            />
          )}
        </div>
      )}

      <ul className="list-disc ps-5 text-xs text-sand-500">
        <li>{t.noteViews}</li>
        <li>{data.include_demo ? t.noteDemoIncluded : t.noteDemoExcluded}</li>
        <li>{t.noteAI}</li>
      </ul>
    </div>
  );
}

export function RangeForm({
  dict,
  data,
  hidden = {},
}: {
  dict: Dictionary;
  data: AnalyticsOverview;
  hidden?: Record<string, string>;
}) {
  const t = dict.analytics;
  return (
    <form method="get" className="flex flex-wrap items-end gap-3 text-sm">
      {Object.entries(hidden).map(([k, v]) => (
        <input key={k} type="hidden" name={k} value={v} />
      ))}
      <label className="flex flex-col gap-1">
        {t.from}
        <input type="date" name="date_from" defaultValue={data.date_from} className="field" />
      </label>
      <label className="flex flex-col gap-1">
        {t.to}
        <input type="date" name="date_to" defaultValue={data.date_to} className="field" />
      </label>
      <label className="flex items-center gap-2">
        <input type="checkbox" name="include_demo" value="1" defaultChecked={data.include_demo} />
        {t.includeDemo}
      </label>
      <button type="submit" className="rounded bg-brand-700 px-3 py-1.5 font-medium text-on-accent">
        {t.apply}
      </button>
    </form>
  );
}
