import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { ActionButton } from "@/features/admin/ActionButton";
import type { BillingConfig, MyBilling } from "@/features/billing/types";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import { formatDate, formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function MyBillingPage() {
  await requireUser();
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const b = dict.billing;
  const [config, data] = await Promise.all([
    serverApiFetch<BillingConfig>("/api/v1/billing/config"),
    serverApiFetch<MyBilling>("/api/v1/me/billing"),
  ]);
  const sub = data.subscription;
  const plan = data.subscription_plan;
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-bold text-brand-900">{b.myBilling}</h1>
      {config.demo && <Alert tone="warning">{b.demoBanner}</Alert>}
      <section className="rounded-lg border border-sand-200 bg-surface p-4">
        <h2 className="mb-2 font-semibold">{b.subscription}</h2>
        {sub && plan ? (
          <div className="flex flex-col gap-2 text-sm">
            <p className="font-medium">{locale === "en" ? plan.name_en : plan.name_ar}</p>
            <p>
              {b.periodEnds}: {formatDate(sub.current_period_end, locale)} · {sub.credits_remaining}{" "}
              {b.credits}
            </p>
            {sub.cancel_at_period_end ? (
              <p className="text-sand-600">{b.cancelRequested}</p>
            ) : (
              <div>
                <ActionButton dict={dict} label={b.cancel} path="/api/v1/me/subscription/cancel" />
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-sand-500">
            {b.noSubscription}{" "}
            <Link href="/pricing" className="text-accent">
              {b.pricingTitle}
            </Link>
          </p>
        )}
      </section>
      <section className="rounded-lg border border-sand-200 bg-surface p-4">
        <h2 className="mb-2 font-semibold">{b.payments}</h2>
        {data.payments.length === 0 ? (
          <p className="text-sm text-sand-500">{b.noPayments}</p>
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {data.payments.map((p) => (
              <li
                key={p.id}
                className="flex flex-wrap justify-between gap-2 border-t border-sand-100 py-1"
              >
                <span>{formatDate(p.created_at, locale)}</span>
                <span>{formatPrice(p.amount, p.currency, locale)}</span>
                <span>
                  {b.statuses[p.status]}
                  {p.is_demo ? ` · ${dict.listing.demo}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {data.promotions.length > 0 && (
        <section className="rounded-lg border border-sand-200 bg-surface p-4">
          <h2 className="mb-2 font-semibold">{b.promotions}</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {data.promotions.map((p) => (
              <li key={p.id}>
                <Link href={`/dashboard/properties/${p.property_id}`} className="text-accent">
                  {formatDate(p.starts_at, locale)} → {formatDate(p.ends_at, locale)}
                </Link>
                {p.canceled_at ? ` · ${b.statuses.CANCELED}` : ""}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
