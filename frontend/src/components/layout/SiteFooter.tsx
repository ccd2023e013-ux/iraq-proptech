import Link from "next/link";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";

import { BrandMark } from "./SiteHeader";

export function SiteFooter({ dict, locale }: { dict: Dictionary; locale: Locale }) {
  return (
    <footer className="mt-28 border-t border-hairline">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-10 text-sm text-ink-3 sm:px-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-md">
          <p className="flex items-center gap-2 font-display text-base font-semibold text-ink">
            <BrandMark className="size-6" />
            {locale === "ar" ? "مَكان" : "MAKAN"}
          </p>
          <p className="mt-2">{dict.footer.tagline}</p>
          <p className="mt-3 text-xs">{dict.footer.demoNotice}</p>
        </div>
        <nav aria-label="footer" className="flex flex-wrap gap-x-6 gap-y-2">
          <Link href="/properties" className="transition-colors hover:text-ink">
            {dict.nav.properties}
          </Link>
          <Link href="/map" className="transition-colors hover:text-ink">
            {dict.nav.map}
          </Link>
          <Link href="/pricing" className="transition-colors hover:text-ink">
            {dict.footer.pricing}
          </Link>
          <Link href="/status" className="transition-colors hover:text-ink">
            {dict.footer.status}
          </Link>
        </nav>
      </div>
    </footer>
  );
}
