import { ActionButton } from "@/features/admin/ActionButton";
import { PlanForm } from "@/features/billing/PlanForm";
import type { BillingConfig, Payment, Plan } from "@/features/billing/types";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";
import { formatDate, formatPrice } from "@/lib/format";
import type { Currency } from "@/types/property";

export const dynamic = "force-dynamic";

interface Summary {
  revenue: { currency: Currency; is_demo: boolean; payments: number; amount: string }[];
  active_subscriptions: number;
}

export default async function AdminBillingPage() {
  await requirePermission("billing.manage");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const b = dict.billing;
  const [config, plans, payments, summary] = await Promise.all([
    serverApiFetch<BillingConfig>("/api/v1/billing/config"),
    serverApiFetch<Plan[]>("/api/v1/admin/billing/plans"),
    serverApiFetch<{ items: Payment[] }>("/api/v1/admin/billing/payments?page_size=50"),
    serverApiFetch<Summary>("/api/v1/admin/billing/summary"),
  ]);
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-brand-900">{dict.admin.billing}</h1>
      <p className="font-mono text-xs" dir="ltr">
        PAYMENT_PROVIDER={config.provider} · enabled={String(config.enabled)}
      </p>
      {config.demo && <p className="rounded bg-gold-100 p-2 text-sm">{b.demoBanner}</p>}

      <section className="grid gap-3 sm:grid-cols-3">
        {summary.revenue.map((r) => (
          <div
            key={`${r.currency}-${r.is_demo}`}
            className="rounded-lg border border-sand-200 bg-white p-3"
          >
            <p className="text-xs text-sand-500">
              {b.revenue} · {r.is_demo ? b.demoRevenue : b.realRevenue}
            </p>
            <p className="text-lg font-semibold">{formatPrice(r.amount, r.currency, locale)}</p>
            <p className="text-xs text-sand-500">{r.payments}</p>
          </div>
        ))}
        <div className="rounded-lg border border-sand-200 bg-white p-3">
          <p className="text-xs text-sand-500">{b.activeSubscriptions}</p>
          <p className="text-lg font-semibold">{summary.active_subscriptions}</p>
        </div>
      </section>

      <section className="rounded-lg border border-sand-200 bg-white p-4">
        <h2 className="mb-3 font-semibold">{b.plans}</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {plans.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <span className="font-mono text-xs" dir="ltr">
                  {p.code}
                </span>{" "}
                · {locale === "en" ? p.name_en : p.name_ar} · {b.kinds[p.kind]} ·{" "}
                {formatPrice(p.price_amount, p.currency, locale)} · {p.duration_days} {b.days}
                {p.is_demo ? ` · ${dict.listing.demo}` : ""}
              </span>
              <ActionButton
                dict={dict}
                label={p.is_active ? b.deactivate : b.activate}
                path={`/api/v1/admin/billing/plans/${p.id}`}
                method="PATCH"
                body={{ is_active: !p.is_active }}
              />
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-sand-200 bg-white p-4">
        <h2 className="mb-3 font-semibold">{b.newPlan}</h2>
        <PlanForm dict={dict} />
      </section>

      <section className="rounded-lg border border-sand-200 bg-white p-4">
        <h2 className="mb-3 font-semibold">{b.payments}</h2>
        {payments.items.length === 0 ? (
          <p className="text-sm text-sand-500">{b.noPayments}</p>
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {payments.items.map((p) => (
              <li
                key={p.id}
                className="flex flex-wrap items-center justify-between gap-2 border-t border-sand-100 py-1"
              >
                <span>
                  {formatDate(p.created_at, locale)} · {formatPrice(p.amount, p.currency, locale)} ·{" "}
                  {b.statuses[p.status]}
                  {p.is_demo ? ` · ${dict.listing.demo}` : ""}
                </span>
                {p.status === "SUCCEEDED" && (
                  <ActionButton
                    dict={dict}
                    label={b.refund}
                    path={`/api/v1/admin/billing/payments/${p.id}/refund`}
                    body={{ reason: "{text}" }}
                    prompt={b.refundReason}
                    tone="bad"
                  />
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
