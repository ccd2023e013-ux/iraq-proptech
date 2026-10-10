import Link from "next/link";

import { ActionButton } from "@/features/admin/ActionButton";
import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";
import { first, type RawParams } from "@/lib/search";

export const dynamic = "force-dynamic";

const STATUSES = ["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"] as const;

interface AdminReport {
  id: string;
  target_type: "PROPERTY" | "USER" | "AGENCY";
  target_id: string;
  reason: string;
  details: string | null;
  status: (typeof STATUSES)[number];
  created_at: string;
  target_label: string | null;
  open_reports_on_target: number;
  resolution_note: string | null;
}

export default async function ReportsPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  const me = await requirePermission("reports.review");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const requested = first((await searchParams).status);
  const status = STATUSES.find((s) => s === requested) ?? "OPEN";
  const reports = await serverApiFetch<{ items: AdminReport[]; total: number }>(
    `/api/v1/admin/reports?status=${status}&page_size=50`,
  );
  const canSuspendUsers = me.permissions.includes("users.suspend");

  return (
    <div className="flex flex-col gap-4">
      <h1 className="display-md text-ink">{a.reports}</h1>
      <nav className="flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <Link
            key={s}
            href={`/admin/reports?status=${s}`}
            aria-current={s === status ? "page" : undefined}
            className={`rounded-full border px-3 py-1 text-sm ${s === status ? "border-brand-600 bg-brand-600 text-on-accent" : "border-sand-200 bg-surface"}`}
          >
            {a.reportStatuses[s]}
          </Link>
        ))}
      </nav>
      {reports.items.length === 0 && <p className="text-sand-500">{a.emptyQueue}</p>}
      <ul className="flex flex-col gap-3">
        {reports.items.map((r) => {
          const open = r.status === "OPEN" || r.status === "IN_REVIEW";
          const resolve = (action: string) => ({ outcome: "RESOLVED", note: "{text}", action });
          return (
            <li
              key={r.id}
              className="flex flex-col gap-2 surface-1 rounded-[var(--radius-card)] p-4 text-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">
                  {a.targetTypes[r.target_type]} ·{" "}
                  {r.target_type === "PROPERTY" ? (
                    <Link
                      href={`/properties/${r.target_id}`}
                      className="text-accent hover:underline"
                    >
                      {r.target_label ?? r.target_id}
                    </Link>
                  ) : (
                    (r.target_label ?? r.target_id)
                  )}
                </span>
                <span className="text-xs text-sand-500">
                  {formatDateTime(r.created_at, locale)}
                </span>
              </div>
              <p>
                <span className="rounded bg-danger/10 px-2 py-0.5 text-xs text-danger">
                  {a.reportReasons[r.reason as keyof typeof a.reportReasons] ?? r.reason}
                </span>
                <span className="ms-2 text-xs text-sand-500 tabular">
                  {a.openReports}: {r.open_reports_on_target}
                </span>
              </p>
              {r.details && <p className="text-sand-700">{r.details}</p>}
              {r.resolution_note && <p className="text-xs text-sand-500">{r.resolution_note}</p>}
              {open && (
                <div className="flex flex-wrap gap-2">
                  {r.status === "OPEN" && (
                    <ActionButton
                      dict={dict}
                      label={a.takeIt}
                      path={`/api/v1/admin/reports/${r.id}/assign`}
                    />
                  )}
                  <ActionButton
                    dict={dict}
                    label={a.dismiss}
                    path={`/api/v1/admin/reports/${r.id}/resolve`}
                    body={{ outcome: "DISMISSED", note: "{text}" }}
                    prompt={a.notePrompt}
                  />
                  <ActionButton
                    dict={dict}
                    label={a.resolve}
                    path={`/api/v1/admin/reports/${r.id}/resolve`}
                    body={resolve("NONE")}
                    prompt={a.notePrompt}
                    tone="good"
                  />
                  {r.target_type === "PROPERTY" && (
                    <ActionButton
                      dict={dict}
                      label={a.suspendListing}
                      path={`/api/v1/admin/reports/${r.id}/resolve`}
                      body={resolve("SUSPEND_LISTING")}
                      prompt={a.notePrompt}
                      tone="bad"
                    />
                  )}
                  {r.target_type === "USER" && canSuspendUsers && (
                    <ActionButton
                      dict={dict}
                      label={a.suspendUser}
                      path={`/api/v1/admin/reports/${r.id}/resolve`}
                      body={resolve("SUSPEND_USER")}
                      prompt={a.notePrompt}
                      tone="bad"
                    />
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
