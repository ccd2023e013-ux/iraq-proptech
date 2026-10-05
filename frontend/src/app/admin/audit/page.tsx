import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";
import { first, type RawParams } from "@/lib/search";

export const dynamic = "force-dynamic";

interface AuditRow {
  id: string;
  occurred_at: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
}

export default async function AuditPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  await requirePermission("audit.read");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const action = (first((await searchParams).action) ?? "").trim();
  const rows = await serverApiFetch<{ items: AuditRow[]; total: number }>(
    `/api/v1/admin/audit-logs?page_size=100${action ? `&action=${encodeURIComponent(action)}` : ""}`,
  );
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-brand-900">{a.audit}</h1>
      <form method="get">
        <input
          name="action"
          defaultValue={action}
          placeholder="property.moderation.approve"
          aria-label={a.action}
          dir="ltr"
          className="h-10 w-full max-w-md rounded-lg border border-sand-200 px-3 text-sm"
        />
      </form>
      <div className="overflow-x-auto rounded-[var(--radius-card)] border border-sand-200 bg-surface">
        <table className="w-full min-w-[800px] text-xs">
          <thead>
            <tr className="border-b border-sand-200 text-sand-500">
              <th className="p-2 text-start">{a.time}</th>
              <th className="p-2 text-start">{a.action}</th>
              <th className="p-2 text-start">{a.resource}</th>
              <th className="p-2 text-start">{a.actor}</th>
              <th className="p-2 text-start">IP</th>
            </tr>
          </thead>
          <tbody>
            {rows.items.map((r) => (
              <tr key={r.id} className="border-b border-sand-100 align-top">
                <td className="p-2 whitespace-nowrap">{formatDateTime(r.occurred_at, locale)}</td>
                <td className="p-2 font-mono" dir="ltr">
                  {r.action}
                </td>
                <td className="p-2 font-mono" dir="ltr">
                  {r.resource_type}:{r.resource_id?.slice(0, 8)}
                </td>
                <td className="p-2 font-mono" dir="ltr">
                  {r.actor_user_id?.slice(0, 8) ?? "system"}
                </td>
                <td className="p-2 font-mono" dir="ltr">
                  {r.ip_address}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
