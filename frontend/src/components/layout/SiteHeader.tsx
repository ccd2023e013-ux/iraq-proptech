import Link from "next/link";
import type { ReactNode } from "react";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import type { ThemeChoice } from "@/lib/theme";
import type { Me } from "@/types/auth";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { MobileMenu } from "./MobileMenu";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

/** MAKAN mark: a place pin over the bend of the Shatt al-Arab, in a rounded tile. */
export function BrandMark({ className = "size-8" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 32 32" className={className}>
      <rect width="32" height="32" rx="9" className="fill-accent-fill" />
      <path
        d="M6 22c4-1 6-4 10-4s6 2 10 0"
        fill="none"
        stroke="#04130d"
        strokeOpacity="0.45"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <path
        d="M16 6.5a5.5 5.5 0 0 0-5.5 5.5c0 4 5.5 8.5 5.5 8.5s5.5-4.5 5.5-8.5A5.5 5.5 0 0 0 16 6.5Z"
        fill="#04130d"
      />
      <circle cx="16" cy="12" r="2" className="fill-accent-fill" />
    </svg>
  );
}

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="rounded-full px-3 py-1.5 text-ink-2 transition hover:bg-fill hover:text-ink"
    >
      {children}
    </Link>
  );
}

export function SiteHeader({
  dict,
  locale,
  me,
  unread = 0,
  theme = "system",
}: {
  dict: Dictionary;
  locale: Locale;
  me: Me | null;
  unread?: number;
  theme?: ThemeChoice;
}) {
  const links = [
    { href: "/properties", label: dict.nav.properties },
    { href: "/map", label: dict.nav.map },
    { href: "/future", label: dict.future.title },
    { href: "/pricing", label: dict.billing.pricingTitle },
    ...(me
      ? [
          { href: "/favorites", label: dict.nav.favorites },
          { href: "/saved-searches", label: dict.savedSearches.title },
        ]
      : []),
  ];
  return (
    <header className="sticky top-0 z-30 border-b border-hairline bg-glass backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5" aria-label={dict.nav.home}>
            <BrandMark />
            <span className="font-display text-[17px] font-semibold tracking-tight whitespace-nowrap text-ink max-[380px]:hidden">
              {locale === "ar" ? "مَكان" : "MAKAN"}
            </span>
          </Link>
          <nav aria-label="primary" className="hidden items-center gap-1 text-sm md:flex">
            {links.map((l) => (
              <NavLink key={l.href} href={l.href}>
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex shrink-0 items-center gap-1 sm:gap-1.5">
          {me && (
            <Link
              href="/dashboard/properties/new"
              className="hidden h-9 items-center rounded-full px-3 text-sm font-medium text-accent ring-1 ring-inset ring-accent/40 transition hover:bg-accent-tint lg:inline-flex"
            >
              {dict.nav.addProperty}
            </Link>
          )}
          <ThemeToggle initial={theme} labels={dict.theme} />
          <LanguageSwitcher current={locale} label={dict.nav.switchLanguage} />
          {me && (
            <Link
              href="/notifications"
              aria-label={`${dict.notifications.title}${unread ? ` (${unread})` : ""}`}
              className="relative grid size-9 place-items-center rounded-full text-ink-2 transition hover:bg-fill hover:text-ink"
            >
              <svg
                aria-hidden
                viewBox="0 0 24 24"
                className="size-[18px]"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M6 9a6 6 0 1 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9Z" />
                <path d="M10 20a2.2 2.2 0 0 0 4 0" />
              </svg>
              {unread > 0 && (
                <span className="absolute -end-0.5 -top-0.5 min-w-4 rounded-full bg-danger px-1 text-center text-[10px] font-bold leading-4 text-white tabular">
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
                className="hidden h-9 items-center rounded-full px-3 text-sm font-medium text-ink-2 transition hover:bg-fill hover:text-ink sm:inline-flex"
              >
                {dict.nav.login}
              </Link>
              <Link
                href="/register"
                className="inline-flex h-9 items-center rounded-full bg-accent-fill px-3.5 text-sm font-medium whitespace-nowrap text-on-accent shadow-soft transition hover:bg-accent-fill-hover"
              >
                {dict.nav.register}
              </Link>
            </>
          )}
          <MobileMenu
            label={dict.nav.menu}
            links={[
              { href: "/", label: dict.nav.home },
              ...links,
              ...(me ? [] : [{ href: "/login", label: dict.nav.login }]),
            ]}
          />
        </div>
      </div>
    </header>
  );
}
