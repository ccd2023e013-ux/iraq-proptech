import type { Metadata } from "next";
import Link from "next/link";

import { TrustBadge } from "@/components/ui/TrustBadge";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import type { DevelopmentCollection } from "@/types/development";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.future.title, description: dict.future.subtitle };
}

const STATUS_TONE: Record<string, string> = {
  UNDER_CONSTRUCTION: "bg-accent-tint text-accent",
  TRIAL_OPERATION: "bg-accent-tint text-accent",
  COMPLETED: "bg-fill text-ink-2",
  OPPORTUNITY: "bg-gold-100 text-gold-700",
};

export default async function FuturePage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const f = dict.future;
  const data = await serverApiFetch<DevelopmentCollection>(
    "/api/v1/development/projects?evidence=true",
  ).catch(() => null);
  const projects = data?.features ?? [];
  const lons = projects.map((p) => p.geometry.coordinates[0]);
  const lats = projects.map((p) => p.geometry.coordinates[1]);
  const allBbox = projects.length
    ? [
        Math.min(...lons) - 0.05,
        Math.min(...lats) - 0.05,
        Math.max(...lons) + 0.05,
        Math.max(...lats) + 0.05,
      ]
        .map((v) => v.toFixed(3))
        .join(",")
    : null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-10 px-4 py-10 sm:px-6">
      <header className="flex flex-col gap-3">
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">{f.title}</h1>
        <p className="max-w-2xl text-lg text-ink-2">{f.subtitle}</p>
        <p className="max-w-2xl rounded-[var(--radius-control)] bg-fill px-4 py-3 text-sm text-ink-2">
          {f.honesty}
        </p>
        {allBbox && (
          <Link
            href={`/map?bbox=${allBbox}&layer=future`}
            className="self-start text-sm font-medium text-accent underline-offset-4 hover:underline"
          >
            {f.allOnMap}
          </Link>
        )}
      </header>

      {projects.length === 0 && <p className="text-ink-2">{f.empty}</p>}

      <ol className="flex flex-col divide-y divide-hairline border-y border-hairline">
        {projects.map(({ properties: p, geometry }) => {
          const name = (locale === "en" && p.name_en) || p.name_ar;
          const summary = (locale === "en" && p.summary_en) || p.summary_ar;
          const timeline = (locale === "en" && p.timeline_en) || p.timeline_ar;
          const [lon, lat] = geometry.coordinates;
          const d = 0.06;
          return (
            <li
              key={p.id}
              id={p.slug}
              className="flex scroll-mt-24 flex-col gap-4 py-8"
              data-testid="future-project"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span
                  className={`rounded-full px-2.5 py-1 font-medium ${STATUS_TONE[p.status] ?? "bg-fill text-ink-2"}`}
                >
                  {(f.statuses as Record<string, string>)[p.status] ?? p.status}
                </span>
                <span className="text-ink-3">
                  {(f.categories as Record<string, string>)[p.category] ?? p.category}
                </span>
                <TrustBadge kind="source">
                  {f.confidenceLabel}: {f.confidence[p.confidence]}
                </TrustBadge>
              </div>
              <h2 className="font-display text-2xl font-semibold tracking-tight text-ink">
                {name}
              </h2>
              <p className="max-w-[68ch] leading-7 text-ink">{summary}</p>
              <dl className="grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-ink-3">{f.timeline}</dt>
                  <dd className="text-ink">{timeline ?? f.noTimeline}</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-3">{f.location}</dt>
                  <dd className="text-ink">
                    {f.precision[p.location_precision]}
                    {p.location_note && (
                      <>
                        {" — "}
                        <span dir="auto">{p.location_note}</span>
                      </>
                    )}{" "}
                    <Link
                      href={`/map?bbox=${[lon - d, lat - d, lon + d, lat + d].map((v) => v.toFixed(3)).join(",")}&layer=future`}
                      className="text-accent underline-offset-4 hover:underline"
                    >
                      {f.showOnMap}
                    </Link>
                  </dd>
                </div>
              </dl>
              {p.evidence && p.evidence.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-ink-3">{f.evidence}</h3>
                  <ul className="mt-2 flex flex-col gap-2">
                    {p.evidence.map((e) => (
                      <li
                        key={`${e.url}-${e.supports}`}
                        className="rounded-[var(--radius-control)] bg-fill px-4 py-3 text-sm"
                      >
                        <p className="font-medium text-ink">
                          {e.source.organization}
                          <span className="ms-2 text-xs font-normal text-ink-3">
                            {f.published}: {e.published_on ?? f.undated} · {f.retrieved}:{" "}
                            {e.retrieved_at.slice(0, 10)}
                          </span>
                        </p>
                        {e.excerpt && (
                          <p className="mt-1 text-ink-2" dir="auto">
                            <q>{e.excerpt}</q>
                          </p>
                        )}
                        <a
                          href={e.url}
                          target="_blank"
                          rel="noopener noreferrer nofollow"
                          className="mt-1 inline-block text-accent underline-offset-4 hover:underline"
                          dir="ltr"
                        >
                          {f.openSource}: {e.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
