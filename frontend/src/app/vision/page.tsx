import { PageHeader } from "@/components/ui/PageHeader";
import type { Metadata } from "next";
import Link from "next/link";

import { type ConceptOut, VisionStudio } from "@/features/vision/VisionStudio";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import { first, type RawParams } from "@/lib/search";
import type { Property } from "@/types/property";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.vision.title, description: dict.vision.subtitle };
}

const UUID = /^[0-9a-f-]{36}$/i;

export default async function VisionPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  const params = await searchParams;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const v = dict.vision;
  const me = await getCurrentUser();
  const rawId = first(params.property_id);
  const propertyId = rawId && UUID.test(rawId) ? rawId : null;
  const property = propertyId
    ? await serverApiFetch<Property>(`/api/v1/properties/${propertyId}`).catch(() => null)
    : null;
  const recent = me
    ? await serverApiFetch<ConceptOut[]>("/api/v1/vision/concepts").catch(() => [])
    : [];
  const cover = property?.media.find((m) => m.kind === "IMAGE")?.url ?? null;
  const title = property ? (locale === "en" && property.title_en) || property.title_ar : null;
  const next = `/vision${propertyId ? `?property_id=${propertyId}` : ""}`;

  return (
    <div className="page flex flex-col gap-8 pb-8">
      <PageHeader title={v.title} lede={v.subtitle} />
      {me ? (
        <VisionStudio
          dict={dict}
          propertyId={property ? propertyId : null}
          propertyTitle={title}
          currentImage={cover}
          recent={propertyId ? recent.filter((c) => c.property_id === propertyId) : recent}
        />
      ) : (
        <div className="flex max-w-2xl flex-col items-start gap-4 rounded-[var(--radius-card)] bg-surface p-8 shadow-[inset_0_0_0_1px_var(--hairline)]">
          <p className="rounded-[var(--radius-tag)] bg-gold-100 px-2.5 py-1 text-xs font-semibold text-gold-700 shadow-[inset_0_0_0_1px_var(--gold-line)]">
            {v.label}
          </p>
          <p className="text-lg text-ink-2">{v.signIn}</p>
          <Link href={`/login?next=${encodeURIComponent(next)}`} className="btn btn-primary">
            {v.signInButton}
          </Link>
        </div>
      )}
    </div>
  );
}
