import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Arabic } from "next/font/google";
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/layout/SiteHeader";
import { CompareBar } from "@/features/compare/CompareControls";
import { getDictionary } from "@/i18n";
import { directionOf } from "@/i18n/config";
import { getRequestLocale } from "@/i18n/server";
import { getCurrentUser } from "@/lib/auth/session";

import "./globals.css";

const arabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-arabic",
  display: "swap",
});

const latin = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-latin",
  display: "swap",
});

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.meta.title, description: dict.meta.description };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#1d504d",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const me = await getCurrentUser();

  return (
    <html
      lang={locale}
      dir={directionOf(locale)}
      className={`${arabic.variable} ${latin.variable}`}
    >
      <body className="min-h-dvh antialiased">
        <SiteHeader dict={dict} locale={locale} me={me} />
        <main>{children}</main>
        <CompareBar dict={dict} />
      </body>
    </html>
  );
}
