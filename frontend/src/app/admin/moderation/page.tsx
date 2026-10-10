import Link from "next/link";

import { ModerationActions } from "@/features/admin/ModerationActions";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";
import { formatDateTime } from "@/features/crm/labels";

export const dynamic = "force-dynamic";

interface QueueItem {
  property_id: string;
  reference_code: string;
  title_ar: string;
  status: string;
  needs_review: boolean;
  is_demo: boolean;
  submitted_at: string;
  open_reports: number;
  quality_score: number;
}

interface Risk {
  result: { risk_level: string; signals: { signal: string; severity: string }[] };
}

export default async function ModerationPage() {
  await requirePermission("properties.moderate");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const queue = await serverApiFetch<{ items: QueueItem[]; total: number }>(
    "/api/v1/admin/moderation/queue?page_size=50",
  );
  const risks = await Promise.all(
    queue.items.map((item) =>
      serverApiFetch<Risk>(`/api/v1/ai/listings/${item.property_id}/risk`).catch(() => null),
    ),
  );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="display-md text-ink">
        {a.moderation}{" "}
        <span className="text-base font-normal text-sand-500 tabular">({queue.total})</span>
      </h1>
      {queue.items.length === 0 && <p className="text-sand-500">{a.emptyQueue}</p>}
      <ul className="flex flex-col gap-3">
        {queue.items.map((item, i) => {
          const risk = risks[i]?.result;
          return (
            <li
              key={item.property_id}
              className="flex flex-col gap-2 surface-1 rounded-[var(--radius-card)] p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Link
                  href={`/properties/${item.property_id}`}
                  className="font-semibold text-brand-800 hover:underline"
                >
                  {item.title_ar}
                </Link>
                <span className="font-mono text-xs text-sand-500" dir="ltr">
                  {item.reference_code}
                </span>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded bg-sand-100 px-2 py-0.5">
                  {dict.listing.statuses[item.status as keyof typeof dict.listing.statuses] ??
                    item.status}
                </span>
                {item.needs_review && (
                  <span className="rounded bg-gold-100 px-2 py-0.5 text-gold-700">{a.flagged}</span>
                )}
                {item.is_demo && <span className="rounded bg-sand-200 px-2 py-0.5">DEMO</span>}
                <span className="rounded bg-sand-100 px-2 py-0.5 tabular">
                  {a.quality}: {item.quality_score}
                </span>
                {item.open_reports > 0 && (
                  <span className="rounded bg-danger/10 px-2 py-0.5 text-danger tabular">
                    {a.openReports}: {item.open_reports}
                  </span>
                )}
                {risk && risk.risk_level !== "none" && (
                  <span className="rounded bg-danger/10 px-2 py-0.5 text-danger">
                    {dict.ai.badge}: {risk.risk_level} ·{" "}
                    {risk.signals.map((s) => s.signal).join(", ")}
                  </span>
                )}
                <span className="text-sand-500">{formatDateTime(item.submitted_at, locale)}</span>
              </div>
              <ModerationActions dict={dict} propertyId={item.property_id} status={item.status} />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
