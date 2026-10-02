import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { requireUser } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

const ADMIN_SECTIONS = [
  ["/admin", "overview", "analytics.all"],
  ["/admin/moderation", "moderation", "properties.moderate"],
  ["/admin/reports", "reports", "reports.review"],
  ["/admin/verification", "verification", "properties.verify"],
  ["/admin/users", "users", "users.read"],
  ["/admin/audit", "audit", "audit.read"],
  ["/admin/ai", "aiUsage", "ai.admin"],
  ["/admin/webhooks", "webhooks", "automation.manage"],
  ["/admin/jobs", "jobs", "automation.manage"],
  ["/admin/settings", "settings", "settings.manage"],
  ["/admin/system", "system", "analytics.all"],
] as const;

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const me = await requireUser();
  const dict = getDictionary(await getRequestLocale());
  const sections = ADMIN_SECTIONS.filter(([, , perm]) => me.permissions.includes(perm));
  if (sections.length === 0) redirect("/dashboard?denied=1");

  return (
    <div className="mx-auto grid max-w-[1400px] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[220px_1fr]">
      <nav
        aria-label={dict.admin.title}
        className="flex flex-col gap-1 lg:sticky lg:top-20 lg:self-start"
      >
        <p className="mb-2 text-sm font-bold text-brand-900">{dict.admin.title}</p>
        {sections.map(([href, key]) => (
          <Link
            key={href}
            href={href}
            className="rounded-md px-3 py-2 text-sm text-sand-700 hover:bg-sand-100"
          >
            {dict.admin[key]}
          </Link>
        ))}
      </nav>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
