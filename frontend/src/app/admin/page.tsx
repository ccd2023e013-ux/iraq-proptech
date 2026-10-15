import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
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
  const actions: [string, number, string][] = (
    [
      [a.pendingReview, s.pending_review, "/admin/moderation"],
      [a.reportsOpen, s.reports_open, "/admin/reports"],
      [a.errors24h, s.errors_24h, "/admin/system"],
      [a.aiFallbacks, s.ai_fallbacks_24h, "/admin/ai"],
    ] as [string, number, string][]
  ).filter(([, n]) => n > 0);
  const platform: [string, number][] = [
    [a.usersTotal, s.users_total],
    [a.newUsers, s.users_new_7d],
    [a.leadsTotal, s.leads_total],
    [a.inquiries7d, s.inquiries_7d],
    [a.aiCalls, s.ai_calls_24h],
    [a.demoListings, s.listings_demo],
  ];
  const statuses = Object.entries(s.listings_by_status).sort((x, y) => y[1] - x[1]);
  const totalListings = statuses.reduce((n, [, v]) => n + v, 0);
  const TONE: Record<string, string> = {
    APPROVED: "bg-accent-fill",
    PENDING_REVIEW: "bg-spatial-fill",
    DRAFT: "bg-ink-3",
    REJECTED: "bg-danger",
    SUSPENDED: "bg-gold-500",
  };
  return (
    <div className="flex flex-col gap-10">
      <PageHeader title={a.overview} size="md" />

      <section aria-labelledby="admin-attention" className="flex flex-col gap-3">
        <h2 id="admin-attention" className="title text-ink">
          {a.attention}
        </h2>
        {actions.length === 0 ? (
          <p className="flex items-center gap-2 text-ink-2">
            <Icon name="check" className="size-5 text-accent" strokeWidth={2.2} />
            {a.allClear}
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {actions.map(([label, n, href]) => (
              <li key={label}>
                <Link
                  href={href}
                  className="group flex items-center justify-between gap-3 rounded-[var(--radius-card)] bg-danger/8 p-5 shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--critical)_30%,transparent)] hover:bg-danger/12"
                >
                  <span className="flex flex-col gap-1">
                    <span className="kpi text-3xl text-danger">{n}</span>
                    <span className="text-[14px] text-ink">{label}</span>
                  </span>
                  <Icon name="chevron" className="size-5 text-ink-3" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="admin-listings" className="flex flex-col gap-3">
        <h2 id="admin-listings" className="title text-ink">
          {a.listingsByStatus}
          <span className="ms-2 text-ink-3 tabular">{totalListings}</span>
        </h2>
        <div className="flex h-3 overflow-hidden rounded-full bg-fill [gap:2px]">
          {statuses.map(([status, n]) => (
            <span
              key={status}
              className={TONE[status] ?? "bg-hairline-strong"}
              style={{ width: `${(n / Math.max(1, totalListings)) * 100}%` }}
            />
          ))}
        </div>
        <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-2">
          {statuses.map(([status, n]) => (
            <li key={status} className="flex items-center gap-2">
              <span
                aria-hidden
                className={`size-2.5 rounded-full ${TONE[status] ?? "bg-hairline-strong"}`}
              />
              {dict.listing.statuses[status as keyof typeof dict.listing.statuses] ?? status}
              <span className="font-medium text-ink tabular">{n}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="admin-platform" className="flex flex-col gap-3">
        <h2 id="admin-platform" className="title text-ink">
          {a.platform}
        </h2>
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-card)] bg-hairline sm:grid-cols-3 xl:grid-cols-6">
          {platform.map(([label, value]) => (
            <div key={label} className="flex flex-col gap-1 bg-surface p-5">
              <dt className="meta">{label}</dt>
              <dd className="kpi text-2xl text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
