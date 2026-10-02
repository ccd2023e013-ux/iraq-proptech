import Link from "next/link";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";

import { LanguageSwitcher } from "./LanguageSwitcher";

export function SiteHeader({ dict, locale }: { dict: Dictionary; locale: Locale }) {
  return (
    <header className="sticky top-0 z-30 border-b border-sand-200 bg-sand-50/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-bold text-brand-800">
          <span
            aria-hidden
            className="grid size-9 place-items-center rounded-xl bg-brand-700 text-lg text-gold-300"
          >
            ع
          </span>
          <span className="text-lg">{locale === "ar" ? "عقار العراق" : "Iraq PropTech"}</span>
        </Link>
        <nav aria-label="primary" className="hidden items-center gap-6 text-sm md:flex">
          <Link href="/" className="text-sand-700 hover:text-brand-700">
            {dict.nav.home}
          </Link>
          <span className="cursor-not-allowed text-sand-500" aria-disabled>
            {dict.nav.properties}
          </span>
          <span className="cursor-not-allowed text-sand-500" aria-disabled>
            {dict.nav.map}
          </span>
        </nav>
        <LanguageSwitcher current={locale} label={dict.nav.switchLanguage} />
      </div>
    </header>
  );
}
