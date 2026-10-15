import type { Metadata } from "next";

import credits from "@/data/demo-photo-credits.json";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";

interface Credit {
  file: string;
  kind: string;
  title: string;
  author: string;
  licence: string;
  licence_url: string;
  source: string;
}

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.credits.title };
}

/**
 * Attribution for the representative DEMO photos (Wikimedia Commons, Flickr): title,
 * author, licence with its link, source page and the changes made — what the
 * CC BY and CC BY-SA licences ask for. The list is a copy of the backend's
 * app/demo_photos/manifest.json (a test keeps the two identical).
 */
export default async function CreditsPage() {
  const dict = getDictionary(await getRequestLocale());
  const c = dict.credits;
  const rows = credits as Credit[];
  const kinds = Array.from(new Set(rows.map((r) => r.kind)));
  return (
    <div className="mx-auto grid max-w-[1320px] gap-10 px-4 py-12 sm:px-6 md:grid-cols-12 md:py-16 lg:px-8">
      <header className="flex flex-col gap-4 md:col-span-4">
        <h1 className="display-lg text-ink">{c.title}</h1>
        <p className="text-ink-2">{c.intro}</p>
        <p className="caption">
          {c.changed} {c.shareAlike}
        </p>
      </header>
      <div className="flex flex-col gap-12 md:col-span-8">
        {kinds.map((kind) => (
          <section key={kind} aria-labelledby={`credits-${kind}`}>
            <h2 id={`credits-${kind}`} className="title mb-3 text-ink">
              {c.kinds[kind as keyof typeof c.kinds] ?? kind}
            </h2>
            <ul className="border-t border-hairline">
              {rows
                .filter((r) => r.kind === kind)
                .map((r) => (
                  <li
                    key={r.file}
                    className="grid gap-1 border-b border-hairline py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-6"
                  >
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <a
                        href={r.source}
                        rel="noopener noreferrer"
                        target="_blank"
                        className="link w-fit text-sm font-medium break-all"
                        dir="auto"
                      >
                        {r.title}
                      </a>
                      <p className="caption">
                        {c.author}: <span dir="auto">{r.author}</span>
                      </p>
                    </div>
                    <p className="meta shrink-0 sm:text-end">
                      {r.licence_url ? (
                        <a
                          href={r.licence_url}
                          rel="noopener noreferrer license"
                          target="_blank"
                          className="link"
                        >
                          {r.licence}
                        </a>
                      ) : (
                        r.licence
                      )}
                    </p>
                  </li>
                ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
