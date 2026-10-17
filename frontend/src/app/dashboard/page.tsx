import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Icon, type IconName } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { SafeImage } from "@/components/ui/SafeImage";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import { hasPermission } from "@/lib/auth/routing";
import { formatDateTime } from "@/features/crm/labels";
import type { Conversation, CrmDashboard } from "@/types/crm";
import type { PropertyCard } from "@/types/property";

export const dynamic = "force-dynamic";

interface Page<T> {
  items: T[];
  total: number;
}

type Row = { label: string; count: number; href: string; icon: IconName; urgent?: boolean };

/**
 * The agent's day: what needs action first (inquiries, follow-ups, listings
 * returned for changes, unread messages), then the state of their listings and
 * what is coming up. Every number links to the place where it is acted on.
 */
export default async function DashboardPage() {
  const me = await requireUser();
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const d = dict.dashboard;
  const c = dict.crm;
  const can = (p: string) => hasPermission(me.permissions, p);
  const canListings = can("properties.create");
  const canLeads = ["leads.read_own", "leads.read_agency", "leads.read_any"].some(can);
  const [listings, board, conversations] = await Promise.all([
    canListings
      ? serverApiFetch<Page<PropertyCard>>("/api/v1/me/properties?page_size=100").catch(() => null)
      : null,
    canLeads ? serverApiFetch<CrmDashboard>("/api/v1/crm/dashboard").catch(() => null) : null,
    serverApiFetch<Conversation[]>("/api/v1/me/conversations").catch(() => [] as Conversation[]),
  ]);

  const byStatus = new Map<string, number>();
  for (const p of listings?.items ?? []) byStatus.set(p.status, (byStatus.get(p.status) ?? 0) + 1);
  const unread = conversations.reduce((n, c2) => n + (c2.unread ?? 0), 0);

  const candidates: Row[] = [
    ...(board
      ? [
          {
            label: c.overdueFollowUps,
            count: board.overdue_follow_ups,
            href: "/dashboard/crm",
            icon: "bell" as const,
            urgent: true,
          },
          {
            label: c.tasksOverdue,
            count: board.tasks_overdue,
            href: "/dashboard/crm/tasks",
            icon: "alert" as const,
            urgent: true,
          },
          {
            label: c.tasksToday,
            count: board.tasks_due_today,
            href: "/dashboard/crm/tasks",
            icon: "calendar" as const,
          },
          {
            label: c.newThisWeek,
            count: board.new_last_7_days,
            href: "/dashboard/crm",
            icon: "user" as const,
          },
        ]
      : []),
    { label: d.unreadMessages, count: unread, href: "/messages", icon: "bell" },
    ...(listings
      ? [
          {
            label: d.listingsRejected,
            count: byStatus.get("REJECTED") ?? 0,
            href: "/dashboard/properties",
            icon: "alert" as const,
            urgent: true,
          },
          {
            label: d.listingsDraft,
            count: byStatus.get("DRAFT") ?? 0,
            href: "/dashboard/properties",
            icon: "document" as const,
          },
          {
            label: d.listingsExpired,
            count: byStatus.get("EXPIRED") ?? 0,
            href: "/dashboard/properties",
            icon: "refresh" as const,
          },
          {
            label: d.listingsPending,
            count: byStatus.get("PENDING_REVIEW") ?? 0,
            href: "/dashboard/properties",
            icon: "info" as const,
          },
        ]
      : []),
  ];
  const rows = candidates.filter((r) => r.count > 0);
  rows.sort((a, b) => Number(!!b.urgent) - Number(!!a.urgent));

  const STATUS_TONE: Record<string, string> = {
    APPROVED: "bg-accent-fill",
    PENDING_REVIEW: "bg-spatial-fill",
    DRAFT: "bg-ink-3",
    REJECTED: "bg-danger",
    EXPIRED: "bg-gold-500",
  };
  const total = listings?.items.length ?? 0;
  const statusEntries = [...byStatus.entries()].sort((a, b) => b[1] - a[1]);

  const more = [
    ...(canListings ? [{ href: "/dashboard/properties", label: dict.myListings.title }] : []),
    ...(canLeads ? [{ href: "/dashboard/crm", label: c.title }] : []),
    ...(["analytics.own", "analytics.agency"].some(can)
      ? [{ href: "/dashboard/analytics", label: dict.analytics.title }]
      : []),
    ...([
      "analytics.all",
      "properties.moderate",
      "reports.review",
      "users.read",
      "settings.manage",
    ].some(can)
      ? [{ href: "/admin", label: dict.admin.title }]
      : []),
    { href: "/messages", label: dict.messages.title },
    { href: "/saved-searches", label: dict.savedSearches.title },
    { href: "/dashboard/agency", label: dict.agency.title },
    { href: "/account/billing", label: dict.billing.myBilling },
    { href: "/account", label: dict.nav.account },
  ];

  return (
    <div className="page flex flex-col gap-10 pb-10">
      <PageHeader
        context={`${d.welcome} · ${new Date().toLocaleDateString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-GB", { weekday: "long", day: "numeric", month: "long" })}`}
        title={me.user.full_name}
        actions={
          <>
            {canListings && (
              <Link href="/dashboard/properties/new" className="btn btn-primary">
                <Icon name="plus" className="size-4" />
                {d.addListing}
              </Link>
            )}
            {canLeads && (
              <Link href="/dashboard/crm" className="btn btn-secondary">
                {c.title}
              </Link>
            )}
          </>
        }
      />
      {!me.user.email_verified && <Alert tone="warning">{d.emailNotVerified}</Alert>}

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-12 [&>*]:min-w-0">
        {/* What needs action, most urgent first. */}
        <section aria-labelledby="attention" className="flex flex-col gap-4 lg:col-span-7">
          <h2 id="attention" className="title text-ink">
            {d.attention}
          </h2>
          {rows.length === 0 ? (
            <div className="flex items-start gap-4 border-y border-hairline py-6">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-fill text-on-accent">
                <Icon name="check" className="size-5" strokeWidth={2.2} />
              </span>
              <div>
                <p className="font-medium text-ink">{d.upToDate}</p>
                <p className="mt-1 text-[15px] text-ink-2">{d.upToDateBody}</p>
              </div>
            </div>
          ) : (
            <ul className="flex flex-col divide-y divide-hairline border-y border-hairline-strong">
              {rows.map((r) => (
                <li key={r.label}>
                  <Link
                    href={r.href}
                    className="group flex items-center gap-4 py-4 pe-2 transition-colors hover:bg-fill/60"
                  >
                    <span
                      className={`grid size-10 shrink-0 place-items-center rounded-full ${r.urgent ? "bg-danger/12 text-danger" : "bg-fill text-ink-2"}`}
                    >
                      <Icon name={r.icon} className="size-5" />
                    </span>
                    <span className="min-w-0 flex-1 text-[15px] text-ink">{r.label}</span>
                    <span className={`kpi text-2xl ${r.urgent ? "text-danger" : "text-ink"}`}>
                      {r.count}
                    </span>
                    <Icon
                      name="chevron"
                      className="size-4 text-ink-3 transition-transform group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {board && board.upcoming_appointments.length > 0 && (
            <div className="mt-6 flex flex-col gap-3">
              <h2 className="title text-ink">{d.upcoming}</h2>
              <ol className="flex flex-col border-s-2 border-hairline ps-5">
                {board.upcoming_appointments.slice(0, 5).map((ap) => (
                  <li key={ap.id} className="relative py-2.5">
                    <span
                      aria-hidden
                      className="absolute -start-[1.6rem] top-4 size-2.5 rounded-full bg-spatial-fill shadow-[0_0_0_3px_var(--canvas)]"
                    />
                    <Link
                      href={`/dashboard/crm/leads/${ap.lead_id}`}
                      className="flex flex-col hover:text-accent"
                    >
                      <span className="font-medium text-ink tabular">
                        {formatDateTime(ap.starts_at, locale)}
                      </span>
                      <span className="meta">
                        {[ap.location_text, c.appointmentStatuses[ap.status]]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </Link>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>

        <aside className="flex flex-col gap-8 lg:col-span-5">
          {listings && total > 0 && (
            <section aria-labelledby="your-listings" className="flex flex-col gap-4">
              <div className="flex items-baseline justify-between gap-3">
                <h2 id="your-listings" className="title text-ink">
                  {d.yourListings}
                </h2>
                <Link href="/dashboard/properties" className="link text-sm">
                  {d.open}
                </Link>
              </div>
              {/* Status mix: one bar, labelled segments (never colour alone). */}
              <div className="flex h-2.5 overflow-hidden rounded-full bg-fill [gap:2px]">
                {statusEntries.map(([status, n]) => (
                  <span
                    key={status}
                    className={STATUS_TONE[status] ?? "bg-hairline-strong"}
                    style={{ width: `${(n / total) * 100}%` }}
                  />
                ))}
              </div>
              <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-ink-2">
                {statusEntries.map(([status, n]) => (
                  <li key={status} className="flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className={`size-2 rounded-full ${STATUS_TONE[status] ?? "bg-hairline-strong"}`}
                    />
                    {dict.listing.statuses[status as keyof typeof dict.listing.statuses] ?? status}
                    <span className="font-medium text-ink tabular">{n}</span>
                  </li>
                ))}
              </ul>
              <p className="meta mt-2">{d.recent}</p>
              <ul className="flex flex-col gap-1">
                {listings.items.slice(0, 4).map((p) => (
                  <li key={p.id}>
                    <Link
                      href={`/dashboard/properties/${p.id}`}
                      className="flex items-center gap-3 rounded-[var(--radius-control)] p-1.5 hover:bg-fill/60"
                    >
                      <span className="relative h-12 w-16 shrink-0 overflow-hidden rounded-[8px] bg-fill">
                        {p.cover_url && (
                          <SafeImage
                            src={p.cover_url}
                            alt=""
                            fallbackLabel="—"
                            className="photo size-full object-cover"
                          />
                        )}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14px] text-ink">
                          {locale === "en" && p.title_en ? p.title_en : p.title_ar}
                        </span>
                        <span className="caption flex items-center gap-1.5">
                          <span
                            aria-hidden
                            className={`size-1.5 rounded-full ${STATUS_TONE[p.status] ?? "bg-hairline-strong"}`}
                          />
                          {dict.listing.statuses[p.status]}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <nav aria-labelledby="everything" className="flex flex-col gap-2">
            <h2 id="everything" className="label">
              {d.everything}
            </h2>
            <ul className="flex flex-col">
              {more.map((link) => (
                <li key={link.href} className="border-t border-hairline first:border-t-0">
                  <Link
                    href={link.href}
                    className="group flex items-center justify-between py-3 text-[15px] text-ink hover:text-accent"
                  >
                    {link.label}
                    <Icon name="chevron" className="size-4 text-ink-3" />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </aside>
      </div>
    </div>
  );
}
