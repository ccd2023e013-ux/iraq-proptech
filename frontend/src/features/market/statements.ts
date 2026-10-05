import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { formatPrice } from "@/lib/format";
import type { MarketStatement } from "@/types/market";
import type { Currency } from "@/types/property";

type Messages = Dictionary["market"]["m"];

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(values[name] ?? ""));
}

export function num(value: unknown, locale: Locale): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value ?? "");
  return n.toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US");
}

function money(value: unknown, currency: unknown, locale: Locale): string {
  return (
    formatPrice(String(value), (currency === "USD" ? "USD" : "IQD") as Currency, locale) ??
    String(value ?? "")
  );
}

function month(value: unknown, locale: Locale): string {
  const [y, m] = String(value).split("-").map(Number);
  if (!y || !m) return String(value ?? "");
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString(
    locale === "ar" ? "ar-IQ-u-nu-latn" : "en-GB",
    { month: "long", year: "numeric", timeZone: "UTC" },
  );
}

function day(value: unknown, locale: Locale): string {
  const d = new Date(`${String(value)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return String(value ?? "");
  return d.toLocaleDateString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

/**
 * A typed market statement in the visitor's language. AI interpretations carry
 * their own text; everything else is a message key plus values from the API, so
 * no number on the page is written by the frontend.
 */
export function renderMarketStatement(
  s: MarketStatement,
  dict: Dictionary,
  locale: Locale,
): string | null {
  if (s.kind === "AI_INTERPRETATION" || s.kind === "SIMULATION") return s.text ?? null;
  const m: Messages = dict.market.m;
  const p = s.params;
  const purposes = dict.listing.purposes as Record<string, string>;
  const type = String((locale === "ar" ? p.type_ar : p.type_en) ?? p.type_code ?? "");
  const purposeLabel = purposes[String(p.purpose)] ?? String(p.purpose ?? "");
  const purposeText = locale === "ar" ? purposeLabel : purposeLabel.toLowerCase();
  switch (s.key) {
    case "fact.active_listings":
      return Number(p.demo_count)
        ? fill(m["fact.active_listings_demo"], {
            count: num(p.count, locale),
            demo: num(p.demo_count, locale),
          })
        : fill(m["fact.active_listings"], { count: num(p.count, locale) });
    case "fact.by_purpose": {
      const counts = (p.counts ?? {}) as Record<string, number>;
      return Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .map(([code, n]) => `${purposes[code] ?? code}: ${num(n, locale)}`)
        .join(locale === "ar" ? "، " : ", ");
    }
    case "fact.by_type":
      return null; // shown in the segments table
    case "fact.new_listings_30d":
      return fill(m["fact.new_listings_30d"], { count: num(p.count, locale) });
    case "fact.listings_with_price_change":
      return fill(m["fact.listings_with_price_change"], {
        count: num(p.count, locale),
        of: num(p.of, locale),
      });
    case "fact.demand_30d":
      return fill(m["fact.demand_30d"], {
        days: num(p.days, locale),
        views: num(p.views, locale),
        favorites: num(p.favorites, locale),
        inquiries: num(p.inquiries, locale),
      });
    case "fact.possible_duplicate_pairs":
      return fill(m["fact.possible_duplicate_pairs"], { pairs: num(p.pairs, locale) });
    case "observed.segment_median":
      return fill(m["observed.segment_median"], {
        type,
        purpose: purposeText,
        median: money(p.median, p.currency, locale),
        p25: money(p.p25, p.currency, locale),
        p75: money(p.p75, p.currency, locale),
      });
    case "observed.price_per_m2_change": {
      const change = Number(p.change_pct);
      return fill(m["observed.price_per_m2_change"], {
        type,
        purpose: purposeText,
        change: `${change > 0 ? "+" : ""}${num(change, locale)}`,
        from: month(p.from_month, locale),
        to: month(p.to_month, locale),
      });
    }
    case "observed.median_price_change": {
      const change = Number(p.change_pct);
      return fill(m["observed.median_price_change"], {
        change: `${change > 0 ? "+" : ""}${num(change, locale)}`,
      });
    }
    case "observed.median_days_on_market":
      return fill(m["observed.median_days_on_market"], { days: num(p.days, locale) });
    case "observed.median_active_age":
      return fill(m["observed.median_active_age"], { days: num(p.days, locale) });
    case "observed.supply_change":
      return fill(m["observed.supply_change"], {
        from_count: num(p.from_count, locale),
        to_count: num(p.to_count, locale),
        from: day(p.from_day, locale),
        to: day(p.to_day, locale),
      });
    case "observed.area_breakdown":
      return fill(m["observed.area_breakdown"], { areas: num(p.areas, locale) });
    default:
      return null;
  }
}
