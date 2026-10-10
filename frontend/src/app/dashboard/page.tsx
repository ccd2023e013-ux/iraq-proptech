import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Icon } from "@/components/ui/Icon";
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
      ? [{ href: "/dashboard/properties", label: dict.myListings.title, icon: "grid" as const }]
      : []),
    ...(["leads.read_own", "leads.read_agency", "leads.read_any"].some((p) =>
      hasPermission(me.permissions, p),
    )
      ? [{ href: "/dashboard/crm", label: dict.crm.title, icon: "user" as const }]
      : []),
    ...(["analytics.own", "analytics.agency"].some((p) => hasPermission(me.permissions, p))
      ? [{ href: "/dashboard/analytics", label: dict.analytics.title, icon: "market" as const }]
      : []),
    ...([
      "analytics.all",
      "properties.moderate",
      "reports.review",
      "users.read",
      "settings.manage",
    ].some((p) => hasPermission(me.permissions, p))
      ? [{ href: "/admin", label: dict.admin.title, icon: "settings" as const }]
      : []),
    { href: "/messages", label: dict.messages.title, icon: "bell" as const },
    { href: "/saved-searches", label: dict.savedSearches.title, icon: "bookmark" as const },
    { href: "/dashboard/agency", label: dict.agency.title, icon: "home" as const },
    { href: "/account/billing", label: dict.billing.myBilling, icon: "list" as const },
    { href: "/account", label: dict.nav.account, icon: "user" as const },
  ];

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-10 sm:px-6">
      <div className="flex flex-col gap-1">
        <p className="meta">{dict.dashboard.welcome}</p>
        <h1 className="display-md text-ink">{me.user.full_name}</h1>
      </div>
      {!me.user.email_verified && <Alert tone="warning">{dict.dashboard.emailNotVerified}</Alert>}
      <section aria-labelledby="quick-links" className="flex flex-col gap-4">
        <h2 id="quick-links" className="text-sm font-semibold text-ink-2">
          {dict.dashboard.quickLinks}
        </h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {links.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="lift surface-1 group flex items-center gap-3.5 rounded-[var(--radius-card)] px-4 py-4"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-tint text-accent">
                  <Icon name={link.icon} className="size-5" />
                </span>
                <span className="flex-1 font-medium text-ink">{link.label}</span>
                <Icon
                  name="chevron"
                  className="size-4 text-ink-3 transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-soft)] group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5"
                />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
