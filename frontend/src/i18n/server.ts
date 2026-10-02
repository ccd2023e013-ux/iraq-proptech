import "server-only";

import { cookies, headers } from "next/headers";

import { LOCALE_COOKIE, type Locale, resolveLocale } from "./config";

/** Locale for the current request: explicit cookie first, then Accept-Language, then Arabic. */
export async function getRequestLocale(): Promise<Locale> {
  const cookieLocale = (await cookies()).get(LOCALE_COOKIE)?.value;
  if (cookieLocale) return resolveLocale(cookieLocale);

  const accept = (await headers()).get("accept-language") ?? "";
  const primary = accept.split(",")[0]?.trim().slice(0, 2).toLowerCase();
  return resolveLocale(primary === "en" ? "en" : "ar");
}
