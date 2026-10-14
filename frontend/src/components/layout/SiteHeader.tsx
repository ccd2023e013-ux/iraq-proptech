import Link from "next/link";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import type { ThemeChoice } from "@/lib/theme";
import type { Me } from "@/types/auth";

import { Icon } from "@/components/ui/Icon";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { MobileMenu } from "./MobileMenu";
import { PrimaryNav } from "./PrimaryNav";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

/**
 * MAKAN mark: a survey plot (the square) with one fixed point on it (emerald)
 * and the river running beneath (cyan) — "a place, read precisely".
 * Drawn on a 32-unit grid; the frame follows the ink colour of the theme.
 */
export function BrandMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 32 32" className={className}>
      <rect
        x="3.25"
        y="3.25"
        width="25.5"
        height="25.5"
        rx="5"
        fill="none"
        className="stroke-ink"
        strokeWidth="2.5"
      />
      <path
        d="M3.5 22.5c5.5-2.6 9.5-2.6 13.2-.6 3.7 2 7.6 2 11.8-.4"
        fill="none"
        className="stroke-spatial-fill"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <circle cx="19.5" cy="12.5" r="3.6" className="fill-accent-fill" />
    </svg>
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
    { href: "/market", label: dict.market.nav },
    { href: "/future", label: dict.future.title },
    { href: "/pricing", label: dict.billing.pricingTitle },
  ];
  // Personal places live in the account menu on wide screens, in the menu on phones.
  const personal = me
    ? [
        { href: "/favorites", label: dict.nav.favorites },
        { href: "/saved-searches", label: dict.savedSearches.title },
      ]
    : [];
  return (
    // A full-width bar with a hairline base. It is an overlay when content
    // scrolls under it (and on the map), so it is translucent with a blur.
    <header className="sticky top-0 z-[var(--z-header)] h-[var(--header-h)] border-b border-hairline bg-canvas/85 backdrop-blur-xl backdrop-saturate-150">
      <div className="page flex h-full items-stretch justify-between gap-4">
        <div className="flex min-w-0 items-stretch gap-6 lg:gap-8">
          <Link
            href="/"
            className="press flex items-center gap-2.5 self-center rounded-[var(--radius-control)]"
            aria-label={dict.nav.home}
          >
            <BrandMark className="size-8" />
            <span className="font-display text-[21px] leading-none font-semibold tracking-tight whitespace-nowrap text-ink max-[380px]:hidden">
              {locale === "ar" ? "مَكان" : "MAKAN"}
            </span>
          </Link>
          <PrimaryNav items={links} label="primary" />
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {me && (
            <Link
              href="/dashboard/properties/new"
              className="btn btn-quiet btn-sm hidden text-accent hover:text-accent lg:inline-flex"
            >
              <Icon name="plus" className="size-4" strokeWidth={2} />
              {dict.nav.addProperty}
            </Link>
          )}
          <ThemeToggle initial={theme} labels={dict.theme} />
          <LanguageSwitcher current={locale} label={dict.nav.switchLanguage} />
          {me && (
            <Link
              href="/notifications"
              aria-label={`${dict.notifications.title}${unread ? ` (${unread})` : ""}`}
              className="icon-btn relative"
            >
              <Icon name="bell" className="size-[18px]" />
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
              <Link href="/login" className="btn btn-quiet btn-sm hidden sm:inline-flex">
                {dict.nav.login}
              </Link>
              <Link href="/register" className="btn btn-secondary btn-sm ms-1">
                {dict.nav.register}
              </Link>
            </>
          )}
          <MobileMenu
            label={dict.nav.menu}
            links={[
              { href: "/", label: dict.nav.home },
              ...links,
              ...personal,
              ...(me ? [] : [{ href: "/login", label: dict.nav.login }]),
            ]}
          />
        </div>
      </div>
    </header>
  );
}
