import Link from "next/link";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import type { Me } from "@/types/auth";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { UserMenu } from "./UserMenu";

export function SiteHeader({
  dict,
  locale,
  me,
  unread = 0,
}: {
  dict: Dictionary;
  locale: Locale;
  me: Me | null;
  unread?: number;
}) {
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
          <Link href="/properties" className="text-sand-700 hover:text-brand-700">
            {dict.nav.properties}
          </Link>
          <Link href="/map" className="text-sand-700 hover:text-brand-700">
            {dict.nav.map}
          </Link>
          {me && (
            <Link href="/favorites" className="text-sand-700 hover:text-brand-700">
              {dict.nav.favorites}
            </Link>
          )}
          {me && (
            <Link href="/saved-searches" className="text-sand-700 hover:text-brand-700">
              {dict.savedSearches.title}
            </Link>
          )}
          {me && (
            <Link
              href="/dashboard/properties/new"
              className="rounded-lg border border-brand-300 px-3 py-1 font-medium text-brand-700 hover:bg-brand-50"
            >
              {dict.nav.addProperty}
            </Link>
          )}
        </nav>
        <div className="flex items-center gap-2">
          <LanguageSwitcher current={locale} label={dict.nav.switchLanguage} />
          {me && (
            <Link
              href="/notifications"
              aria-label={`${dict.notifications.title}${unread ? ` (${unread})` : ""}`}
              className="relative grid size-9 place-items-center rounded-lg text-sand-700 hover:bg-sand-100"
            >
              <span aria-hidden>🔔</span>
              {unread > 0 && (
                <span className="absolute -end-0.5 -top-0.5 min-w-4 rounded-full bg-danger px-1 text-center text-[10px] font-bold text-white tabular">
                  {unread > 99 ? "99+" : unread}
                </span>
              )}
            </Link>
          )}
          {me ? (
            <UserMenu dict={dict} name={me.user.full_name} />
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-sand-700 hover:text-brand-700"
              >
                {dict.nav.login}
              </Link>
              <Link
                href="/register"
                className="hidden rounded-lg bg-brand-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-800 sm:inline-block"
              >
                {dict.nav.register}
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
