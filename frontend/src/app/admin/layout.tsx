import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { SectionNav } from "@/components/layout/SectionNav";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { requireUser } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

const ADMIN_SECTIONS = [
  ["/admin", "overview", "analytics.all"],
  ["/admin/analytics", "analytics", "analytics.all"],
  ["/admin/moderation", "moderation", "properties.moderate"],
  ["/admin/reports", "reports", "reports.review"],
  ["/admin/verification", "verification", "properties.verify"],
  ["/admin/users", "users", "users.read"],
  ["/admin/audit", "audit", "audit.read"],
  ["/admin/ai", "aiUsage", "ai.admin"],
  ["/admin/webhooks", "webhooks", "automation.manage"],
  ["/admin/jobs", "jobs", "automation.manage"],
  ["/admin/billing", "billing", "billing.manage"],
  ["/admin/settings", "settings", "settings.manage"],
  ["/admin/system", "system", "analytics.all"],
] as const;

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const me = await requireUser();
  const dict = getDictionary(await getRequestLocale());
  const sections = ADMIN_SECTIONS.filter(([, , perm]) => me.permissions.includes(perm));
  if (sections.length === 0) redirect("/dashboard?denied=1");

  return (
    <div className="page grid grid-cols-[minmax(0,1fr)] gap-6 py-6 lg:grid-cols-[232px_minmax(0,1fr)] lg:gap-12 lg:py-10">
      <SectionNav
        title={dict.admin.title}
        root="/admin"
        items={sections.map(([href, key]) => ({ href, label: dict.admin[key] }))}
      />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
