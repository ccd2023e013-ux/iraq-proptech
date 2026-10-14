import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import Link from "next/link";

import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import type { Conversation } from "@/types/crm";

export const dynamic = "force-dynamic";

export default async function MessagesPage() {
  await requireUser();
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const m = dict.messages;
  const conversations = await serverApiFetch<Conversation[]>("/api/v1/me/conversations");

  return (
    <div className="page flex flex-col gap-6 pb-8">
      <PageHeader title={m.title} />
      {conversations.length === 0 ? (
        <EmptyState
          title={m.empty}
          glyph="list"
          action={{ href: "/properties", label: dict.nav.properties }}
        />
      ) : (
        <ul className="flex flex-col divide-y divide-sand-100 surface-1 rounded-[var(--radius-card)]">
          {conversations.map((c) => {
            const counterpart = c.role === "customer" ? c.lister : c.customer;
            const title = c.property
              ? locale === "en" && c.property.title_en
                ? c.property.title_en
                : c.property.title_ar
              : "";
            return (
              <li key={c.id}>
                <Link
                  href={`/messages/${c.id}`}
                  className="flex flex-col gap-1 p-4 hover:bg-sand-50"
                >
                  <span className="flex items-center justify-between gap-3">
                    <span className="font-semibold text-sand-900">
                      {counterpart?.full_name ?? "—"}
                    </span>
                    <span className="text-xs text-sand-500">
                      {formatDateTime(c.last_message_at, locale)}
                    </span>
                  </span>
                  <span className="text-xs text-accent">
                    {c.role === "customer" ? m.asCustomer : m.asLister} · {title}
                  </span>
                  <span className="flex items-center justify-between gap-3">
                    <span className="truncate text-sm text-sand-700">{c.last_message}</span>
                    {c.unread > 0 && (
                      <span className="shrink-0 rounded-[var(--radius-tag)] bg-brand-700 px-2 py-0.5 text-xs text-on-accent tabular">
                        {c.unread} {m.unread}
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
