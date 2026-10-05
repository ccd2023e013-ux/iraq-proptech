import { ActionButton } from "@/features/admin/ActionButton";
import { WebhookForm } from "@/features/admin/WebhookForm";
import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

interface Webhook {
  id: string;
  name: string;
  url: string;
  events: string[];
  is_active: boolean;
  consecutive_failures: number;
  last_status: number | null;
  last_delivery_at: string | null;
}

export default async function WebhooksPage() {
  await requirePermission("automation.manage");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const [hooks, events] = await Promise.all([
    serverApiFetch<Webhook[]>("/api/v1/admin/webhooks"),
    serverApiFetch<string[]>("/api/v1/admin/webhooks/events"),
  ]);
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-brand-900">{a.webhooks}</h1>
      <p className="text-sm text-sand-600">{a.n8nHint}</p>
      {hooks.length === 0 ? (
        <p className="text-sm text-sand-500">{a.noWebhooks}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {hooks.map((h) => (
            <li
              key={h.id}
              className="flex flex-col gap-2 rounded-lg border border-sand-200 bg-surface p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{h.name}</span>
                <span
                  className={`rounded px-2 py-0.5 text-xs ${h.is_active ? "bg-green-100 text-green-800" : "bg-sand-100 text-sand-600"}`}
                >
                  {h.is_active ? a.active : a.disabled}
                </span>
              </div>
              <p className="font-mono text-xs break-all" dir="ltr">
                {h.url}
              </p>
              <p className="text-xs text-sand-600" dir="ltr">
                {h.events.join(", ")}
              </p>
              <p className="text-xs text-sand-500">
                {a.lastStatus}: {h.last_status ?? "—"}
                {h.last_delivery_at
                  ? ` · ${formatDateTime(h.last_delivery_at, locale)}`
                  : ""} · {a.failures}: {h.consecutive_failures}
              </p>
              <div className="flex flex-wrap gap-2">
                <ActionButton
                  dict={dict}
                  label={a.sendTest}
                  path={`/api/v1/admin/webhooks/${h.id}/test`}
                />
                <ActionButton
                  dict={dict}
                  label={h.is_active ? a.disable : a.enable}
                  path={`/api/v1/admin/webhooks/${h.id}`}
                  method="PATCH"
                  body={{ is_active: !h.is_active }}
                />
                <ActionButton
                  dict={dict}
                  label={a.delete}
                  path={`/api/v1/admin/webhooks/${h.id}`}
                  method="DELETE"
                  tone="bad"
                />
              </div>
            </li>
          ))}
        </ul>
      )}
      <section className="rounded-lg border border-sand-200 bg-surface p-4">
        <h2 className="mb-3 font-semibold">{a.newWebhook}</h2>
        <WebhookForm dict={dict} events={events} />
      </section>
    </div>
  );
}
