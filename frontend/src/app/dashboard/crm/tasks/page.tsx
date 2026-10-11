import Link from "next/link";

import { TaskPanel } from "@/features/crm/LeadPanels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireAnyPermission } from "@/lib/auth/guard";
import { first, type RawParams } from "@/lib/search";
import type { Page, Task } from "@/types/crm";

export const dynamic = "force-dynamic";

const FILTERS = ["open", "today", "overdue", "done", "all"] as const;

export default async function TasksPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  const me = await requireAnyPermission(["leads.read_own", "leads.read_agency", "leads.read_any"]);
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const c = dict.crm;
  const requested = first((await searchParams).status);
  const status = FILTERS.find((f) => f === requested) ?? "open";
  const tasks = await serverApiFetch<Page<Task>>(
    `/api/v1/crm/tasks?status=${status}&page_size=100`,
  );

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div>
        <Link href="/dashboard/crm" className="text-sm text-accent">
          {c.dashboard}
        </Link>
        <h1 className="display-md text-ink">{c.tasks}</h1>
      </div>
      <nav className="flex flex-wrap gap-2" aria-label={c.tasks}>
        {FILTERS.map((f) => (
          <Link
            key={f}
            href={`/dashboard/crm/tasks?status=${f}`}
            aria-current={f === status ? "page" : undefined}
            className={`rounded-[var(--radius-control)] border px-3 py-1 text-sm ${f === status ? "border-brand-600 bg-brand-600 text-on-accent" : "border-sand-200 bg-surface"}`}
          >
            {c.taskFilters[f]}
          </Link>
        ))}
      </nav>
      <div className="surface-1 rounded-[var(--radius-card)] p-4">
        <TaskPanel
          dict={dict}
          locale={locale}
          leadId={null}
          tasks={tasks.items}
          canManage={me.permissions.includes("leads.manage")}
        />
      </div>
    </div>
  );
}
