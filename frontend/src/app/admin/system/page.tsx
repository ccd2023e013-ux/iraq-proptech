import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

interface SystemInfo {
  environment: string;
  ai_provider: string;
  database: string;
  postgis?: string;
  migration?: string | null;
  redis: string;
  queue_length: number | null;
}

interface ErrorRow {
  id: string;
  request_id: string | null;
  method: string | null;
  path: string | null;
  error_type: string;
  created_at: string;
}

export default async function SystemPage() {
  await requirePermission("analytics.all");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const [info, errors] = await Promise.all([
    serverApiFetch<SystemInfo>("/api/v1/admin/system"),
    serverApiFetch<{ items: ErrorRow[] }>("/api/v1/admin/errors?page_size=50"),
  ]);
  const rows: [string, string][] = [
    ["APP_ENV", info.environment],
    ["AI_PROVIDER", info.ai_provider],
    [a.database, info.database],
    ["PostGIS", info.postgis ?? "—"],
    [a.migration, info.migration ?? "—"],
    [a.redis, info.redis],
    [a.queueLength, info.queue_length === null ? "—" : String(info.queue_length)],
  ];
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-brand-900">{a.system}</h1>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {rows.map(([k, v]) => (
          <div key={k} className="rounded-lg border border-sand-200 bg-surface p-3">
            <dt className="text-xs text-sand-500">{k}</dt>
            <dd
              className={`font-mono text-sm ${v === "error" || v === "unavailable" ? "text-danger" : ""}`}
              dir="ltr"
            >
              {v}
            </dd>
          </div>
        ))}
      </dl>
      <section>
        <h2 className="mb-2 font-semibold">{a.recentErrors}</h2>
        {errors.items.length === 0 ? (
          <p className="text-sm text-sand-500">{a.noErrors}</p>
        ) : (
          <ul className="flex flex-col gap-1 font-mono text-xs" dir="ltr">
            {errors.items.map((e) => (
              <li key={e.id} className="rounded bg-surface px-3 py-2">
                {formatDateTime(e.created_at, locale)} · {e.method} {e.path} · {e.error_type} ·{" "}
                {e.request_id}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
