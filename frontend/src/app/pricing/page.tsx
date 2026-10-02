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
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div>
        <h1 className="text-2xl font-bold text-brand-900">{b.pricingTitle}</h1>
        <p className="mt-1 text-sand-600">{b.pricingIntro}</p>
      </div>
      {!config.enabled && <Alert tone="info">{b.disabled}</Alert>}
      {config.demo && <Alert tone="warning">{b.demoBanner}</Alert>}
      {plans.length === 0 ? (
        <p className="text-sand-500">{b.noPlans}</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) => (
            <li
              key={plan.id}
              className="flex flex-col gap-3 rounded-xl border border-sand-200 bg-white p-5"
            >
              <span className="text-xs font-medium text-sand-500">{b.kinds[plan.kind]}</span>
              <h2 className="text-lg font-semibold text-brand-900">
                {locale === "en" ? plan.name_en : plan.name_ar}
              </h2>
              <p className="text-2xl font-bold">
                {formatPrice(plan.price_amount, plan.currency, locale)}
              </p>
              <p className="text-sm text-sand-600">
                {plan.duration_days} {b.days}
                {plan.featured_credits > 0 && ` · ${plan.featured_credits} ${b.credits}`}
              </p>
              {(locale === "en" ? plan.description_en : plan.description_ar) && (
                <p className="text-sm">
                  {locale === "en" ? plan.description_en : plan.description_ar}
                </p>
              )}
              <div className="mt-auto">
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
