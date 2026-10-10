import type { Metadata } from "next";

import { Alert } from "@/components/ui/Alert";
import { BuyButton } from "@/features/billing/BuyButton";
import type { BillingConfig, Plan } from "@/features/billing/types";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.billing.pricingTitle };
}

export default async function PricingPage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const b = dict.billing;
  const [config, plans] = await Promise.all([
    serverApiFetch<BillingConfig>("/api/v1/billing/config"),
    serverApiFetch<Plan[]>("/api/v1/billing/plans"),
  ]);
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-12 sm:px-6">
      <header className="flex flex-col items-center gap-3 text-center">
        <h1 className="display-lg text-ink">{b.pricingTitle}</h1>
        <p className="max-w-xl text-ink-2">{b.pricingIntro}</p>
      </header>
      {!config.enabled && <Alert tone="info">{b.disabled}</Alert>}
      {config.demo && <Alert tone="warning">{b.demoBanner}</Alert>}
      {plans.length === 0 ? (
        <p className="text-sand-500">{b.noPlans}</p>
      ) : (
        <ul className="mx-auto grid w-full max-w-3xl gap-5 sm:grid-cols-2">
          {plans.map((plan) => (
            <li
              key={plan.id}
              className={`surface-1 relative flex flex-col gap-3 overflow-hidden rounded-[var(--radius-card)] p-6 ${plan.kind === "SUBSCRIPTION" ? "shadow-[var(--edge),0_0_0_1px_var(--accent-line),var(--shadow-soft)]" : ""}`}
            >
              <span
                className={`w-fit rounded-full px-2.5 py-0.5 text-xs font-medium ${plan.kind === "SUBSCRIPTION" ? "bg-accent-tint text-accent" : "bg-fill text-ink-2"}`}
              >
                {b.kinds[plan.kind]}
              </span>
              <h2 className="font-display text-lg font-semibold tracking-tight text-ink">
                {locale === "en" ? plan.name_en : plan.name_ar}
              </h2>
              <p className="kpi text-4xl text-ink">
                {formatPrice(plan.price_amount, plan.currency, locale)}
              </p>
              <p className="text-sm text-ink-3 tabular">
                {plan.duration_days} {b.days}
                {plan.featured_credits > 0 && ` · ${plan.featured_credits} ${b.credits}`}
              </p>
              {(locale === "en" ? plan.description_en : plan.description_ar) && (
                <p className="text-sm text-ink-2">
                  {locale === "en" ? plan.description_en : plan.description_ar}
                </p>
              )}
              <div className="mt-auto pt-3">
                {plan.kind === "SUBSCRIPTION" && config.enabled ? (
                  <BuyButton
                    dict={dict}
                    planCode={plan.code}
                    label={b.subscribe}
                    loginNext="/pricing"
                  />
                ) : (
                  <p className="text-xs text-sand-500">{b.promotionHint}</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
