import type { Metadata } from "next";
import Link from "next/link";

import { MapPreview, type PreviewTone } from "@/features/map/MapPreview";
import { resolveMapConfig } from "@/lib/map/provider";

import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { stagger } from "@/lib/motion";
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

  // Real counts by status (no invented figures).
  const byStatus = projects.reduce<Record<string, number>>((acc, { properties: p }) => {
    acc[p.status] = (acc[p.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-14">
      {/* Urban-intelligence header: the projects plotted where they are, on a
          survey grid, beside the title. Positions come from the records. */}
      <header className="relative isolate overflow-hidden">
        <div aria-hidden className="stage-grid absolute inset-0 -z-10" />
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 pt-10 pb-6 sm:px-6 md:pt-16 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="flex flex-col gap-5">
            <p className="reveal meta flex items-center gap-2">
              <Icon name="future" className="size-4 text-spatial" />
              {f.layer}
            </p>
            <h1 className="reveal display-xl text-ink" style={stagger(1)}>
              {f.title}
            </h1>
            <p className="reveal max-w-xl text-lg text-ink-2" style={stagger(2)}>
              {f.subtitle}
            </p>
            {projects.length > 0 && (
              <dl className="reveal mt-2 flex flex-wrap gap-x-10 gap-y-4" style={stagger(3)}>
                {Object.entries(byStatus).map(([status, count]) => (
                  <div key={status}>
                    <dd className="kpi text-4xl text-ink">
                      <AnimatedNumber value={count} locale={locale} />
                    </dd>
                    <dt className="meta mt-1.5 flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className={`size-2 rounded-full ${STATUS_DOT[status] ?? "bg-ink-3"}`}
                      />
                      {(f.statuses as Record<string, string>)[status] ?? status}
                    </dt>
                  </div>
                ))}
              </dl>
            )}
            {allBbox && (
              <Link
                href={`/map?bbox=${allBbox}&layer=future`}
                className="press reveal surface-float mt-2 inline-flex h-11 w-fit items-center gap-2 rounded-[var(--radius-control)] px-5 text-sm font-medium text-ink"
                style={stagger(4)}
              >
                <Icon name="map" className="size-4 text-spatial" />
                {f.allOnMap}
              </Link>
            )}
          </div>
          {projects.length > 0 && (
            <figure className="fade-in surface-1 relative rounded-[var(--radius-media)] p-2">
              <MapPreview
                config={resolveMapConfig(process.env)}
                className="h-64 sm:h-80"
                label={projects
                  .map(
                    ({ properties: p }, i) =>
                      `${i + 1}. ${(locale === "en" && p.name_en) || p.name_ar}`,
                  )
                  .join(" ")}
                points={projects.map(({ properties: p, geometry }, i) => ({
                  lon: geometry.coordinates[0],
                  lat: geometry.coordinates[1],
                  precision: p.location_precision === "EXACT" ? "exact" : "area",
                  tone: PREVIEW_TONE[p.status] ?? "muted",
                  label: String(i + 1),
                }))}
              />
            </figure>
          )}
        </div>
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <p className="max-w-2xl rounded-[var(--radius-control)] bg-fill px-4 py-3 text-sm text-ink-2">
            {f.honesty}
          </p>
        </div>
      </header>

      <div className="mx-auto w-full max-w-5xl px-4 sm:px-6">
        {projects.length === 0 && <EmptyState title={f.empty} glyph="future" />}

        <ol className="relative flex flex-col border-s border-hairline">
          {projects.map(({ properties: p, geometry }, index) => {
            const name = (locale === "en" && p.name_en) || p.name_ar;
            const summary = (locale === "en" && p.summary_en) || p.summary_ar;
            const timeline = (locale === "en" && p.timeline_en) || p.timeline_ar;
            const [lon, lat] = geometry.coordinates;
            const d = 0.06;
            return (
              <li
                key={p.id}
                id={p.slug}
                className="reveal relative flex scroll-mt-28 flex-col gap-4 py-10 ps-8 sm:ps-10"
                style={stagger(index)}
                data-testid="future-project"
              >
                <span
                  aria-hidden
                  className={`absolute -start-[7px] top-[2.85rem] size-3.5 rounded-full ring-4 ring-canvas ${STATUS_DOT[p.status] ?? "bg-ink-3"}`}
                />
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  {/* Key to the numbered point on the plot above. */}
                  <span className="grid size-5 place-items-center rounded-full bg-fill text-[11px] font-semibold text-ink-2 tabular">
                    {index + 1}
                  </span>
                  <span
                    className={`rounded-[var(--radius-control)] px-2.5 py-1 font-medium ${STATUS_TONE[p.status] ?? "bg-fill text-ink-2"}`}
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
                <h2 className="display-md text-ink">{name}</h2>
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
                        className="press mt-2 flex h-8 w-fit items-center gap-1.5 rounded-[var(--radius-control)] bg-spatial-tint px-3 text-[13px] font-medium text-spatial"
                      >
                        <Icon name="pin" className="size-3.5" />
                        {f.showOnMap}
                      </Link>
                    </dd>
                  </div>
                </dl>
                {p.evidence && p.evidence.length > 0 && (
                  <details className="group" open={index === 0}>
                    <summary className="chip w-fit cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                      {f.evidence} <span className="tabular">({p.evidence.length})</span>
                      <Icon
                        name="chevron-down"
                        className="size-3.5 transition-transform duration-[var(--duration-base)] group-open:rotate-180"
                      />
                    </summary>
                    <ul className="fade-in mt-3 flex flex-col gap-2">
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
                  </details>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

const STATUS_DOT: Record<string, string> = {
  UNDER_CONSTRUCTION: "bg-accent-fill",
  TRIAL_OPERATION: "bg-accent-fill",
  COMPLETED: "bg-ink-3",
  OPPORTUNITY: "bg-gold-500",
};

const PREVIEW_TONE: Record<string, PreviewTone> = {
  UNDER_CONSTRUCTION: "accent",
  TRIAL_OPERATION: "accent",
  COMPLETED: "muted",
  OPPORTUNITY: "gold",
};
