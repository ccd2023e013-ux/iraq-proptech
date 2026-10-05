import { notFound } from "next/navigation";

import { Alert } from "@/components/ui/Alert";
import { DemoCheckout } from "@/features/billing/DemoCheckout";
import type { Payment, Plan } from "@/features/billing/types";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import { formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function DemoCheckoutPage({ params }: { params: Promise<{ id: string }> }) {
  await requireUser();
  const { id } = await params;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const b = dict.billing;
  let data: { payment: Payment; plan: Plan | null };
  try {
    data = await serverApiFetch(`/api/v1/billing/payments/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    throw error;
  }
  if (!data.payment.is_demo) notFound();
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-bold text-brand-900">{b.checkoutTitle}</h1>
      <Alert tone="warning">{b.demoBanner}</Alert>
      <dl className="rounded-lg border border-sand-200 bg-surface p-4 text-sm">
        <dt className="text-sand-500">{b.plans}</dt>
        <dd className="mb-2 font-medium">
          {data.plan ? (locale === "en" ? data.plan.name_en : data.plan.name_ar) : "—"}
        </dd>
        <dt className="text-sand-500">{b.amount}</dt>
        <dd className="text-lg font-semibold">
          {formatPrice(data.payment.amount, data.payment.currency, locale)}
        </dd>
      </dl>
      <DemoCheckout dict={dict} payment={data.payment} />
    </div>
  );
}
