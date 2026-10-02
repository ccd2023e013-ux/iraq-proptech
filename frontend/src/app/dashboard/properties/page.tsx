import Link from "next/link";

import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/features/listings/StatusPill";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";
import { formatCompactPrice, formatDate } from "@/lib/format";
import type { Page, PropertyCard } from "@/types/property";

export const dynamic = "force-dynamic";

export default async function MyListingsPage() {
  await requirePermission("properties.create");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const page = await serverApiFetch<Page<PropertyCard>>("/api/v1/me/properties?page_size=100");
  const m = dict.myListings;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-brand-900">{m.title}</h1>
        <Link
          href="/dashboard/properties/new"
          className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
        >
          {m.add}
        </Link>
      </div>
      <Card>
        {page.items.length === 0 ? (
          <p className="py-10 text-center text-sand-500">{m.empty}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-start text-sm">
              <thead className="text-xs text-sand-500">
                <tr className="border-b border-sand-200">
                  <th className="py-2 text-start font-medium">{m.reference}</th>
                  <th className="py-2 text-start font-medium">{dict.listingForm.titleAr}</th>
                  <th className="py-2 text-start font-medium">{dict.listingForm.price}</th>
                  <th className="py-2 text-start font-medium">{m.status}</th>
                  <th className="py-2 text-start font-medium">{m.updated}</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-100">
                {page.items.map((p) => (
                  <tr key={p.id}>
                    <td className="py-3 font-mono text-xs" dir="ltr">
                      {p.reference_code}
                    </td>
                    <td className="max-w-xs truncate py-3">{p.title_ar}</td>
                    <td className="py-3 tabular whitespace-nowrap">
                      {p.price_on_request
                        ? dict.listing.priceOnRequest
                        : formatCompactPrice(p.price_amount, p.currency, locale)}
                    </td>
                    <td className="py-3">
                      <StatusPill status={p.status} dict={dict} />
                    </td>
                    <td className="py-3 whitespace-nowrap text-sand-500">
                      {formatDate(p.created_at, locale)}
                    </td>
                    <td className="py-3 text-end">
                      <Link
                        href={`/dashboard/properties/${p.id}`}
                        className="font-medium text-brand-700 hover:underline"
                      >
                        {m.edit}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
