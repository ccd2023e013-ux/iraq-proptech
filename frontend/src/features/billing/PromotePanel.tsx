import { ActionButton } from "@/features/admin/ActionButton";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { formatDate, formatPrice } from "@/lib/format";

import { BuyButton } from "./BuyButton";
import type { BillingConfig, Plan } from "./types";

/** Shown on a published listing's management page. Server component. */
export function PromotePanel({
  dict,
  locale,
  propertyId,
  featuredUntil,
  config,
  plans,
  credits,
}: {
  dict: Dictionary;
  locale: Locale;
  propertyId: string;
  featuredUntil: string | null | undefined;
  config: BillingConfig;
  plans: Plan[];
  credits: number;
}) {
  const b = dict.billing;
  const active = featuredUntil && new Date(featuredUntil) > new Date();
  const promotions = plans.filter((p) => p.kind === "PROMOTION");
  return (
    <div className="flex flex-col gap-3 text-sm">
      {active && (
        <p className="font-medium text-brand-800">
          {b.featuredUntil}: {formatDate(featuredUntil ?? null, locale)}
        </p>
      )}
      {!config.enabled ? (
        <p className="text-sand-500">{b.disabled}</p>
      ) : (
        <>
          {config.demo && <p className="rounded bg-gold-100 p-2 text-xs">{b.demoBanner}</p>}
          <ul className="flex flex-col gap-2">
            {promotions.map((plan) => (
              <li key={plan.id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {locale === "en" ? plan.name_en : plan.name_ar} ·{" "}
                  {formatPrice(plan.price_amount, plan.currency, locale)} · {plan.duration_days}{" "}
                  {b.days}
                </span>
                <BuyButton dict={dict} planCode={plan.code} propertyId={propertyId} label={b.buy} />
              </li>
            ))}
          </ul>
          {promotions.length === 0 && <p className="text-sand-500">{b.noPlans}</p>}
        </>
      )}
      {credits > 0 && (
        <ActionButton
          dict={dict}
          label={`${b.useCredit} (${credits} ${b.creditsLeft})`}
          path="/api/v1/billing/promotions/redeem"
          body={{ property_id: propertyId }}
          tone="good"
        />
      )}
    </div>
  );
}
