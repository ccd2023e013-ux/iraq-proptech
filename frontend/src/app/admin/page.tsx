import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireAnyPermission } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

interface Stats {
  users_total: number;
  users_by_status: Record<string, number>;
  users_new_7d: number;
  listings_by_status: Record<string, number>;
  listings_demo: number;
  pending_review: number;
  agencies_by_status: Record<string, number>;
  reports_open: number;
  leads_total: number;
  inquiries_7d: number;
  ai_calls_24h: number;
  ai_fallbacks_24h: number;
  errors_24h: number;
}

export default async function AdminOverview() {
  await requireAnyPermission(["analytics.all"]);
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const s = await serverApiFetch<Stats>("/api/v1/admin/stats");
  const tiles: [string, number, boolean?][] = [
    [a.usersTotal, s.users_total],
    [a.newUsers, s.users_new_7d],
    [a.pendingReview, s.pending_review, s.pending_review > 0],
    [a.reportsOpen, s.reports_open, s.reports_open > 0],
    [a.leadsTotal, s.leads_total],
    [a.inquiries7d, s.inquiries_7d],
    [a.aiCalls, s.ai_calls_24h],
    [a.aiFallbacks, s.ai_fallbacks_24h, s.ai_fallbacks_24h > 0],
    [a.errors24h, s.errors_24h, s.errors_24h > 0],
    [a.demoListings, s.listings_demo],
  ];
  return (
    <div className="flex flex-col gap-6">
      <h1 className="display-md text-ink">{a.overview}</h1>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {tiles.map(([label, value, alert]) => (
          <div
            key={label}
            className="rounded-[var(--radius-card)] border border-sand-200 bg-surface p-4"
          >
            <dt className="text-xs text-sand-500">{label}</dt>
            <dd className={`kpi mt-1 text-3xl ${alert ? "text-danger" : "text-ink"}`}>{value}</dd>
          </div>
        ))}
      </dl>
      <section className="rounded-[var(--radius-card)] border border-sand-200 bg-surface p-4">
        <h2 className="mb-3 text-sm font-semibold">{a.listingsByStatus}</h2>
        <ul className="flex flex-wrap gap-2 text-sm">
          {Object.entries(s.listings_by_status).map(([status, n]) => (
            <li key={status} className="rounded-full bg-sand-100 px-3 py-1 tabular">
              {dict.listing.statuses[status as keyof typeof dict.listing.statuses] ?? status}: {n}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
