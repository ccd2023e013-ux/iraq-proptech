import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import type { ReactNode } from "react";

import { MobileTabBar } from "@/components/layout/MobileTabBar";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { CompareBar } from "@/features/compare/CompareControls";
import { getDictionary } from "@/i18n";
import { directionOf } from "@/i18n/config";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";

// Fonts are self-hosted from npm (@fontsource): builds work offline and no
// third-party font CDN is contacted at build or run time.
// MAKAN type: Readex Pro for Arabic, Inter for English and numerals.
import "@fontsource-variable/inter/index.css";
import "@fontsource-variable/readex-pro/index.css";
import "./globals.css";

import { SiteFooter } from "@/components/layout/SiteFooter";
import { THEME_COOKIE, type ThemeChoice, parseTheme } from "@/lib/theme";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.meta.title, description: dict.meta.description };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8fafc" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0f17" },
  ],
};

async function themeChoice(): Promise<ThemeChoice> {
  return parseTheme((await cookies()).get(THEME_COOKIE)?.value);
}

async function loadAnnouncement(locale: string): Promise<string | null> {
  try {
    const settings = await serverApiFetch<Record<string, unknown>>("/api/v1/settings/public");
    const text = settings[`site.announcement_${locale}`] ?? settings["site.announcement_ar"];
    return typeof text === "string" && text.trim() ? text.trim() : null;
  } catch {
    return null; // the banner is optional; never break the page
  }
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const me = await getCurrentUser();
  const theme = await themeChoice();
  const [announcement, unread] = await Promise.all([
    loadAnnouncement(locale),
    me
      ? serverApiFetch<{ unread: number }>("/api/v1/me/notifications/unread-count")
          .then((r) => r.unread)
          .catch(() => 0)
      : Promise.resolve(0),
  ]);

  return (
    <html
      lang={locale}
      dir={directionOf(locale)}
      data-theme={theme === "system" ? undefined : theme}
      suppressHydrationWarning
    >
      {/* Phones reserve room at the bottom for the floating tab bar. */}
      <body className="flex min-h-dvh flex-col pb-[var(--tabbar-h)] antialiased">
        {announcement && (
          <div role="status" className="bg-gold-100 px-4 py-2 text-center text-sm text-gold-700">
            {announcement}
          </div>
        )}
        <SiteHeader dict={dict} locale={locale} me={me} unread={unread} theme={theme} />
        <main className="flex-1">{children}</main>
        <SiteFooter dict={dict} locale={locale} />
        <CompareBar dict={dict} />
        <MobileTabBar
          label={dict.nav.menu}
          items={[
            { href: "/", label: dict.nav.home, icon: "home" },
            { href: "/map", label: dict.nav.map, icon: "map" },
            { href: "/properties", label: dict.nav.properties, icon: "grid" },
            { href: "/future", label: dict.future.title, icon: "future" },
            me
              ? { href: "/favorites", label: dict.nav.favorites, icon: "heart" }
              : { href: "/login", label: dict.nav.login, icon: "user" },
          ]}
        />
      </body>
    </html>
  );
}
