import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { requireUser } from "@/lib/auth/guard";
import { hasPermission } from "@/lib/auth/routing";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const me = await requireUser();
  const dict = getDictionary(await getRequestLocale());

  const links = [
    ...(hasPermission(me.permissions, "properties.create")
      ? [{ href: "/dashboard/properties", label: dict.myListings.title }]
      : []),
    ...(["leads.read_own", "leads.read_agency", "leads.read_any"].some((p) =>
      hasPermission(me.permissions, p),
    )
      ? [{ href: "/dashboard/crm", label: dict.crm.title }]
      : []),
    ...(["analytics.own", "analytics.agency"].some((p) => hasPermission(me.permissions, p))
      ? [{ href: "/dashboard/analytics", label: dict.analytics.title }]
      : []),
    ...([
      "analytics.all",
      "properties.moderate",
      "reports.review",
      "users.read",
      "settings.manage",
    ].some((p) => hasPermission(me.permissions, p))
      ? [{ href: "/admin", label: dict.admin.title }]
      : []),
    { href: "/messages", label: dict.messages.title },
    { href: "/saved-searches", label: dict.savedSearches.title },
    { href: "/dashboard/agency", label: dict.agency.title },
    { href: "/account/billing", label: dict.billing.myBilling },
    { href: "/account", label: dict.nav.account },
  ];

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div>
        <p className="text-sm text-sand-500">{dict.dashboard.welcome}</p>
        <h1 className="text-2xl font-bold text-brand-900">{me.user.full_name}</h1>
      </div>
      {!me.user.email_verified && <Alert tone="warning">{dict.dashboard.emailNotVerified}</Alert>}
      <Card title={dict.dashboard.quickLinks}>
        <ul className="grid gap-3 sm:grid-cols-3">
          {links.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="block rounded-lg border border-sand-200 px-4 py-3 font-medium text-brand-800 transition hover:border-brand-300 hover:bg-brand-50"
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
