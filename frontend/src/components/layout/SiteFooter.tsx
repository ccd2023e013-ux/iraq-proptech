import Link from "next/link";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";

import { BrandMark } from "./SiteHeader";

/** An editorial index: the mark and the DEMO notice, then two ruled columns. */
export function SiteFooter({ dict, locale }: { dict: Dictionary; locale: Locale }) {
  const columns = [
    {
      title: dict.footer.explore,
      links: [
        { href: "/properties", label: dict.nav.properties },
        { href: "/map", label: dict.nav.map },
        { href: "/market", label: dict.market.nav },
        { href: "/future", label: dict.future.title },
      ],
    },
    {
      title: dict.footer.platform,
      links: [
        { href: "/search/smart", label: dict.ai.smartSearch },
        { href: "/pricing", label: dict.footer.pricing },
        { href: "/status", label: dict.footer.status },
        { href: "/credits", label: dict.footer.photoCredits },
      ],
    },
  ];
  return (
    <footer className="mt-32 border-t border-hairline">
      <div className="mx-auto grid max-w-[1320px] gap-10 px-4 py-12 sm:px-6 md:grid-cols-12 lg:px-8">
        <div className="flex flex-col gap-3 md:col-span-6 lg:col-span-5">
          <p className="flex items-center gap-2.5 font-display text-lg font-semibold text-ink">
            <BrandMark className="size-6" />
            {locale === "ar" ? "مَكان" : "MAKAN"}
          </p>
          <p className="max-w-sm text-ink-2">{dict.footer.tagline}</p>
          <p className="caption max-w-sm">{dict.footer.demoNotice}</p>
        </div>
        {columns.map((col) => (
          <nav
            key={col.title}
            aria-label={col.title}
            className="flex flex-col md:col-span-3 lg:col-span-2 lg:col-start-auto"
          >
            <p className="meta mb-2 font-medium text-ink-2">{col.title}</p>
            {col.links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="border-b border-hairline py-2.5 text-sm text-ink-2 transition-colors hover:text-ink"
              >
                {l.label}
              </Link>
            ))}
          </nav>
        ))}
      </div>
      <div className="border-t border-hairline">
        <p className="caption mx-auto max-w-[1320px] px-4 py-4 sm:px-6 lg:px-8">
          {dict.footer.mapCredits}
        </p>
      </div>
    </footer>
  );
}
