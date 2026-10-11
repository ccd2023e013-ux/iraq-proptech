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
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10 sm:px-6">
      <header className="flex max-w-2xl flex-col gap-3">
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">{v.title}</h1>
        <p className="text-lg text-ink-2">{v.subtitle}</p>
      </header>
      {me ? (
        <VisionStudio
          dict={dict}
          propertyId={property ? propertyId : null}
          propertyTitle={title}
          currentImage={cover}
          recent={propertyId ? recent.filter((c) => c.property_id === propertyId) : recent}
        />
      ) : (
        <div className="flex flex-col items-start gap-4 rounded-[var(--radius-card)] bg-fill p-6">
          <p className="rounded-[var(--radius-control)] bg-ink px-4 py-2 text-xs font-semibold text-surface">
            {v.label}
          </p>
          <p className="text-ink-2">{v.signIn}</p>
          <Link
            href={`/login?next=${encodeURIComponent(next)}`}
            className="inline-flex h-11 items-center rounded-[var(--radius-control)] bg-accent-fill px-5 font-medium text-on-accent hover:bg-accent-fill-hover"
          >
            {v.signInButton}
          </Link>
        </div>
      )}
    </div>
  );
}
