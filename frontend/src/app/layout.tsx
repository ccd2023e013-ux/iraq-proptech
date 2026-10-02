import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/layout/SiteHeader";
import { CompareBar } from "@/features/compare/CompareControls";
import { getDictionary } from "@/i18n";
import { directionOf } from "@/i18n/config";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";

// Fonts are self-hosted from npm (@fontsource): builds work offline and no
// third-party font CDN is contacted at build or run time.
import "@fontsource/ibm-plex-sans-arabic/400.css";
import "@fontsource/ibm-plex-sans-arabic/500.css";
import "@fontsource/ibm-plex-sans-arabic/600.css";
import "@fontsource/ibm-plex-sans-arabic/700.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/600.css";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.meta.title, description: dict.meta.description };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#1d504d",
};

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
  const announcement = await loadAnnouncement(locale);

  return (
    <html lang={locale} dir={directionOf(locale)}>
      <body className="min-h-dvh antialiased">
        {announcement && (
          <div role="status" className="bg-gold-100 px-4 py-2 text-center text-sm text-gold-700">
            {announcement}
          </div>
        )}
        <SiteHeader dict={dict} locale={locale} me={me} />
        <main>{children}</main>
        <CompareBar dict={dict} />
      </body>
    </html>
  );
}
