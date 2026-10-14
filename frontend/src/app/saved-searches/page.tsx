import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { redirect } from "next/navigation";
import Link from "next/link";

import { SavedSearchActions } from "@/features/search/SavedSearchActions";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { formatDate } from "@/lib/format";
import { filtersToQuery } from "@/lib/search";

export const dynamic = "force-dynamic";

interface SavedSearch {
  id: string;
  name: string;
  filters: Record<string, unknown>;
  alert_frequency: "NONE" | "INSTANT" | "DAILY" | "WEEKLY";
  new_matches: number;
  created_at: string;
}

export default async function SavedSearchesPage() {
  const me = await getCurrentUser();
  if (!me) redirect("/login?next=/saved-searches");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const s = dict.savedSearches;
  const rows = await serverApiFetch<SavedSearch[]>("/api/v1/me/saved-searches");

  return (
    <div className="page flex flex-col gap-6 pb-8">
      <PageHeader title={s.title} />
      {rows.length === 0 ? (
        <EmptyState
          title={s.empty}
          glyph="bookmark"
          action={{ href: "/properties", label: dict.nav.properties }}
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((row) => (
            <li
              key={row.id}
              className="flex flex-col gap-3 surface-1 rounded-[var(--radius-card)] p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex flex-col gap-1">
                <span className="font-semibold text-sand-900">
                  {row.name}
                  {row.new_matches > 0 && (
                    <span className="ms-2 rounded-[var(--radius-tag)] bg-gold-500 px-2 py-0.5 text-xs font-bold text-[#1d1405] tabular">
                      {row.new_matches} {s.newMatches}
                    </span>
                  )}
                </span>
                <span className="text-xs text-sand-500">{formatDate(row.created_at, locale)}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href={`/properties?${filtersToQuery(row.filters)}`}
                  className="rounded-lg bg-brand-700 px-3 py-1.5 text-sm font-medium text-on-accent"
                >
                  {s.open}
                </Link>
                <SavedSearchActions dict={dict} id={row.id} frequency={row.alert_frequency} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
