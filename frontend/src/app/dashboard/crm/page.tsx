import { PageHeader } from "@/components/ui/PageHeader";
import type { Metadata } from "next";
import Link from "next/link";

import { Card } from "@/components/ui/Card";
import { NewLeadForm } from "@/features/crm/NewLeadForm";
import { StageSelect } from "@/features/crm/StageSelect";
import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireAnyPermission } from "@/lib/auth/guard";
import type { CrmDashboard, Lead, LeadStatus, Page } from "@/types/crm";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.crm.title };
}

export default async function CrmPage() {
  const me = await requireAnyPermission(["leads.read_own", "leads.read_agency", "leads.read_any"]);
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const c = dict.crm;
  const [board, statuses, leads] = await Promise.all([
    serverApiFetch<CrmDashboard>("/api/v1/crm/dashboard"),
    serverApiFetch<LeadStatus[]>("/api/v1/crm/statuses"),
    serverApiFetch<Page<Lead>>("/api/v1/crm/leads?open_only=true&page_size=100"),
  ]);
  const prioritized = await serverApiFetch<{
    result: { items: { lead_id: string; score: number }[] };
  }>("/api/v1/ai/leads/prioritized").catch(() => null);
  const leadById = new Map(leads.items.map((l) => [l.id, l]));
  const columns = statuses.filter((s) => s.is_active && !s.is_terminal);
  const canManage = me.permissions.includes("leads.manage");
  const stats: [string, string | number, string?][] = [
    [c.totalOpen, board.total_open],
    [c.newThisWeek, board.new_last_7_days],
    [c.overdueFollowUps, board.overdue_follow_ups, board.overdue_follow_ups ? "text-danger" : ""],
    [c.tasksToday, board.tasks_due_today],
    [c.tasksOverdue, board.tasks_overdue, board.tasks_overdue ? "text-danger" : ""],
    [
      c.conversion,
      board.conversion_rate === null ? c.noData : `${Math.round(board.conversion_rate * 100)}%`,
    ],
  ];

  return (
    <div className="page flex flex-col gap-8 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader title={c.dashboard} />
        <nav className="flex flex-wrap gap-2 text-sm">
          <Link href="/dashboard/crm/tasks" className="btn btn-secondary btn-sm">
            {c.tasks}
          </Link>
          <Link href="/messages" className="btn btn-secondary btn-sm">
            {dict.messages.title}
          </Link>
        </nav>
      </div>

      <dl className="grid grid-cols-2 gap-px overflow-hidden border-y border-hairline-strong bg-hairline sm:grid-cols-3 lg:grid-cols-6">
        {stats.map(([label, value, tone]) => (
          <div key={label} className="flex flex-col gap-1 bg-canvas px-4 py-4">
            <dt className="meta">{label}</dt>
            <dd className={`kpi text-2xl ${tone || "text-ink"}`}>{value}</dd>
          </div>
        ))}
      </dl>

      {canManage && <NewLeadForm dict={dict} />}

      <section aria-labelledby="pipeline-heading" className="flex flex-col gap-3">
        <h2 id="pipeline-heading" className="title text-ink">
          {c.pipeline}
          <span className="caption ms-2 tabular">
            {c.won}: {board.won} · {c.lost}: {board.lost}
          </span>
        </h2>
        <div className="flex gap-3 overflow-x-auto pb-2">
          {columns.map((column) => {
            const inColumn = leads.items.filter((l) => l.status_code === column.code);
            return (
              <div
                key={column.code}
                className="flex w-72 shrink-0 flex-col gap-2 rounded-[var(--radius-card)] bg-fill/60 p-3"
              >
                <h3 className="flex justify-between px-1 pb-1 text-sm font-medium text-ink">
                  {locale === "ar" ? column.name_ar : column.name_en}
                  <span className="text-ink-3 tabular">{inColumn.length}</span>
                </h3>
                {inColumn.length === 0 && <p className="caption px-1">{c.noLeads}</p>}
                {inColumn.map((lead) => (
                  <article
                    key={lead.id}
                    className="flex flex-col gap-1.5 rounded-[var(--radius-control)] bg-surface p-3 shadow-[inset_0_0_0_1px_var(--hairline),0_1px_2px_rgb(0_0_0/0.08)]"
                  >
                    <Link
                      href={`/dashboard/crm/leads/${lead.id}`}
                      className="font-medium text-ink hover:text-accent"
                    >
                      {lead.customer.full_name}
                    </Link>
                    {lead.property && (
                      <span className="truncate text-xs text-ink-3">
                        {locale === "en" && lead.property.title_en
                          ? lead.property.title_en
                          : lead.property.title_ar}
                      </span>
                    )}
                    <span className="text-xs text-ink-3">
                      {c.sources[lead.source]}
                      {lead.priority === "HIGH" && (
                        <span className="ms-1 font-semibold text-danger">
                          · {c.priorities.HIGH}
                        </span>
                      )}
                    </span>
                    {lead.next_follow_up_at && (
                      <span
                        className={`text-xs ${new Date(lead.next_follow_up_at) < new Date() ? "text-danger" : "text-ink-2"}`}
                      >
                        {c.followUp}: {formatDateTime(lead.next_follow_up_at, locale)}
                      </span>
                    )}
                    {lead.assigned_to && (
                      <span className="text-xs text-ink-3">
                        {c.assignedTo}: {lead.assigned_to.full_name}
                      </span>
                    )}
                    {canManage && (
                      <StageSelect
                        dict={dict}
                        locale={locale}
                        leadId={lead.id}
                        current={lead.status_code}
                        statuses={statuses}
                      />
                    )}
                  </article>
                ))}
              </div>
            );
          })}
        </div>
      </section>

      {prioritized && prioritized.result.items.length > 0 && (
        <Card title={dict.ai.prioritized}>
          <ol className="flex flex-col gap-2 text-sm">
            {prioritized.result.items.slice(0, 5).map((item) => {
              const lead = leadById.get(item.lead_id);
              return (
                <li key={item.lead_id} className="flex items-center justify-between gap-3">
                  <Link
                    href={`/dashboard/crm/leads/${item.lead_id}`}
                    className="text-accent hover:underline"
                  >
                    {lead?.customer.full_name ?? item.lead_id}
                  </Link>
                  <span className="rounded bg-brand-50 px-2 py-0.5 text-xs text-brand-800 tabular">
                    {dict.ai.score}: {item.score}
                  </span>
                </li>
              );
            })}
          </ol>
        </Card>
      )}

      <Card title={c.upcoming}>
        {board.upcoming_appointments.length === 0 ? (
          <p className="text-sm text-ink-3">{c.noUpcoming}</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {board.upcoming_appointments.map((a) => (
              <li key={a.id} className="flex justify-between gap-3">
                <Link
                  href={`/dashboard/crm/leads/${a.lead_id}`}
                  className="text-accent hover:underline"
                >
                  {formatDateTime(a.starts_at, locale)}
                </Link>
                <span className="text-ink-3">{a.location_text}</span>
                <span>{c.appointmentStatuses[a.status]}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
