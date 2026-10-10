import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

interface JobRow {
  id: string;
  name: string;
  status: string;
  detail: Record<string, unknown> | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export default async function JobsPage() {
  await requirePermission("automation.manage");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const [jobs, deliveries] = await Promise.all([
    serverApiFetch<JobRow[]>("/api/v1/admin/jobs"),
    serverApiFetch<{ counts: Record<string, number> }>("/api/v1/admin/notifications/deliveries"),
  ]);
  return (
    <div className="flex flex-col gap-6">
      <h1 className="display-md text-ink">{a.jobs}</h1>
      <section>
        <h2 className="mb-2 font-semibold">{a.deliveryCounts}</h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Object.entries(deliveries.counts).map(([k, v]) => (
            <div key={k} className="surface-1 rounded-2xl p-3">
              <dt className="font-mono text-xs text-sand-500">{k}</dt>
              <dd className="text-lg font-semibold">{v}</dd>
            </div>
          ))}
        </dl>
      </section>
      {jobs.length === 0 ? (
        <p className="text-sm text-sand-500">{a.noJobs}</p>
      ) : (
        <ul className="flex flex-col gap-1 font-mono text-xs" dir="ltr">
          {jobs.map((j) => (
            <li
              key={j.id}
              className={`rounded bg-surface px-3 py-2 ${j.status === "FAILED" ? "text-danger" : ""}`}
            >
              {formatDateTime(j.started_at, locale)} · {j.name} · {j.status}
              {j.detail ? ` · ${JSON.stringify(j.detail)}` : ""}
              {j.error ? ` · ${j.error}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
