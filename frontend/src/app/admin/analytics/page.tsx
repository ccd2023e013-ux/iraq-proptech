import { AnalyticsReport, RangeForm } from "@/features/analytics/AnalyticsReport";
import { type AnalyticsOverview, type RangeParams, rangeQuery } from "@/features/analytics/types";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

export default async function PlatformAnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<RangeParams>;
}) {
  await requirePermission("analytics.all");
  const params = await searchParams;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const data = await serverApiFetch<AnalyticsOverview>(
    `/api/v1/analytics/overview?${rangeQuery(params, { scope: "platform" })}`,
  );
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-brand-900">{dict.analytics.platformTitle}</h1>
      <RangeForm dict={dict} data={data} />
      <AnalyticsReport data={data} dict={dict} locale={locale} />
    </div>
  );
}
