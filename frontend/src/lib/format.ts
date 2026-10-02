import type { Locale } from "@/i18n/config";
import type { Currency } from "@/types/property";

/**
 * Prices are displayed exactly in the currency they were listed in.
 * No conversion ever happens here (see docs: currency handling).
 */
export function formatPrice(
  amount: string | number | null,
  currency: Currency,
  locale: Locale,
): string | null {
  if (amount === null || amount === "") return null;
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(value)) return null;
  const number = new Intl.NumberFormat(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US", {
    maximumFractionDigits: currency === "USD" ? 2 : 0,
  }).format(value);
  if (currency === "USD") return locale === "ar" ? `${number} دولار` : `$${number}`;
  return locale === "ar" ? `${number} د.ع` : `${number} IQD`;
}

/** Compact Iraqi-style amounts: 250,000,000 IQD → "250 مليون". */
export function formatCompactPrice(
  amount: string | number | null,
  currency: Currency,
  locale: Locale,
): string | null {
  if (amount === null || amount === "") return null;
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(value)) return null;
  if (currency === "IQD" && value >= 1_000_000) {
    const millions = value / 1_000_000;
    const shown = Number.isInteger(millions) ? String(millions) : millions.toFixed(1);
    return locale === "ar" ? `${shown} مليون د.ع` : `${shown}M IQD`;
  }
  return formatPrice(value, currency, locale);
}

export function formatArea(area: string | number | null, locale: Locale): string | null {
  if (area === null || area === "") return null;
  const value = typeof area === "string" ? Number(area) : area;
  if (!Number.isFinite(value)) return null;
  const number = new Intl.NumberFormat(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US", {
    maximumFractionDigits: 2,
  }).format(value);
  return locale === "ar" ? `${number} م²` : `${number} m²`;
}

export function formatDate(iso: string | null, locale: Locale): string | null {
  if (!iso) return null;
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-GB", {
    dateStyle: "medium",
  }).format(new Date(iso));
}

export function placeName(place: { name_ar: string; name_en: string } | null, locale: Locale) {
  if (!place) return null;
  return locale === "ar" ? place.name_ar : place.name_en;
}
