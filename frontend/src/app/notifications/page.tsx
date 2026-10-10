import Link from "next/link";

import { ActionButton } from "@/features/admin/ActionButton";
import { formatDateTime } from "@/features/crm/labels";
import { NotificationPreferences, type Prefs } from "@/features/notifications/Preferences";
import { Card } from "@/components/ui/Card";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

interface Note {
  id: string;
  kind: string;
  title_ar: string;
  title_en: string;
  body_ar: string | null;
  body_en: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

export default async function NotificationsPage() {
  await requireUser();
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const n = dict.notifications;
  const [page, prefs] = await Promise.all([
    serverApiFetch<{ items: Note[] }>("/api/v1/me/notifications?page_size=50"),
    serverApiFetch<Prefs>("/api/v1/me/notification-preferences"),
  ]);
  const unread = page.items.some((i) => !i.read_at);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="display-md text-ink">{n.title}</h1>
        {unread && (
          <ActionButton
            dict={dict}
            label={n.markAllRead}
            path="/api/v1/me/notifications/read-all"
          />
        )}
      </div>
      {page.items.length === 0 ? (
        <p className="rounded-[var(--radius-card)] border border-dashed border-sand-200 py-12 text-center text-sand-500">
          {n.empty}
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-sand-100 surface-1 rounded-[var(--radius-card)]">
          {page.items.map((item) => {
            const title = locale === "en" ? item.title_en : item.title_ar;
            const body = locale === "en" ? item.body_en : item.body_ar;
            return (
              <li
                key={item.id}
                className={`flex flex-col gap-1 p-4 ${item.read_at ? "" : "bg-brand-50"}`}
              >
                <span className="flex items-center justify-between gap-3">
                  {item.link ? (
                    <Link href={item.link} className="font-semibold text-brand-800 hover:underline">
                      {title}
                    </Link>
                  ) : (
                    <span className="font-semibold">{title}</span>
                  )}
                  <span className="text-xs text-sand-500">
                    {formatDateTime(item.created_at, locale)}
                  </span>
                </span>
                {body && <span className="text-sm text-sand-700">{body}</span>}
              </li>
            );
          })}
        </ul>
      )}
      <Card title={n.preferences}>
        <NotificationPreferences dict={dict} initial={prefs} />
      </Card>
    </div>
  );
}
