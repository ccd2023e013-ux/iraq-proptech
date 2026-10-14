import { PageHeader } from "@/components/ui/PageHeader";
import type { Metadata } from "next";
import { headers } from "next/headers";

import { Studio } from "@/features/studio/Studio";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import { first, type RawParams } from "@/lib/search";
import type { PropertyCard } from "@/types/property";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.studio.title };
}

export default async function StudioPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  await requireUser();
  const params = await searchParams;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const mine = await serverApiFetch<{ items: PropertyCard[] }>(
    "/api/v1/me/properties?page_size=50",
  ).catch(() => ({ items: [] as PropertyCard[] }));
  const listings = mine.items.map((p) => ({
    id: p.id,
    title: (locale === "en" && p.title_en) || p.title_ar,
  }));
  const requested = first(params.property_id) ?? null;
  const host = (await headers()).get("host") ?? "iraq-proptech-web.onrender.com";

  return (
    <div className="page flex flex-col gap-8 pb-8">
      <PageHeader title={dict.studio.title} lede={dict.studio.subtitle} />
      <Studio
        dict={dict}
        locale={locale}
        listings={listings}
        initialPropertyId={listings.some((l) => l.id === requested) ? requested : null}
        site={host}
      />
    </div>
  );
}
