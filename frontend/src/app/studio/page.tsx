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
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10 sm:px-6">
      <header className="flex max-w-2xl flex-col gap-3">
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
          {dict.studio.title}
        </h1>
        <p className="text-lg text-ink-2">{dict.studio.subtitle}</p>
      </header>
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
