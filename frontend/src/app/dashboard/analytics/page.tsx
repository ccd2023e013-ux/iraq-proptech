import Link from "next/link";

import { AnalyticsReport, RangeForm } from "@/features/analytics/AnalyticsReport";
import { type AnalyticsOverview, type RangeParams, rangeQuery } from "@/features/analytics/types";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import { hasPermission } from "@/lib/auth/routing";

export const dynamic = "force-dynamic";

export default async function MyAnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<RangeParams & { scope?: string }>;
}) {
  const me = await requireUser();
  const params = await searchParams;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const t = dict.analytics;
  const canAgency = hasPermission(me.permissions, "analytics.agency");
  const scope = params.scope === "agency" && canAgency ? "agency" : "me";
  const data = await serverApiFetch<AnalyticsOverview>(
    `/api/v1/analytics/overview?${rangeQuery(params, { scope })}`,
  );
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
      <h1 className="display-md text-ink">{t.title}</h1>
      {canAgency && (
        <nav className="flex gap-2 text-sm">
          {(["me", "agency"] as const).map((s) => (
            <Link
              key={s}
              href={`/dashboard/analytics?scope=${s}`}
              aria-current={scope === s ? "page" : undefined}
              className={`rounded-[var(--radius-control)] border px-3 py-1 ${scope === s ? "border-brand-700 bg-brand-700 text-on-accent" : "border-sand-300"}`}
            >
              {s === "me" ? t.myScope : t.agencyScope}
            </Link>
          ))}
        </nav>
      )}
      <RangeForm dict={dict} data={data} hidden={{ scope }} />
      <AnalyticsReport data={data} dict={dict} locale={locale} />
    </div>
  );
}
