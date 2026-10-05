import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { formatPrice } from "@/lib/format";
import type { Statement } from "@/types/intelligence";
import type { Currency } from "@/types/property";

type Messages = Dictionary["intel"]["m"];

function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(values[name] ?? ""));
}

function num(value: unknown, locale: Locale): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value ?? "");
  return n.toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US");
}

function money(value: unknown, currency: unknown, locale: Locale): string {
  return formatPrice(String(value), (currency === "USD" ? "USD" : "IQD") as Currency, locale) ?? "";
}

/**
 * Renders a typed statement in the visitor's language. AI interpretations
 * carry their own text; every other statement is a message key plus values,
 * so facts and estimates read the same in Arabic and English.
 */
export function renderStatement(s: Statement, dict: Dictionary, locale: Locale): string {
  if (s.kind === "AI_INTERPRETATION" || s.kind === "SIMULATION") return s.text ?? "";
  const m: Messages = dict.intel.m;
  const p = s.params;
  const categories = dict.nearby.categories as Record<string, string>;
  const approx = p.approximate ? ` (${m.approximate})` : "";
  switch (s.key) {
    case "fact.asking_price": {
      const period =
        typeof p.rent_period === "string"
          ? ` ${(dict.property.perPeriod as Record<string, string>)[p.rent_period] ?? ""}`
          : "";
      const text = fill(m["fact.asking_price"], {
        price: money(p.amount, p.currency, locale) + period,
      });
      return p.negotiable ? `${text} · ${m["fact.negotiable"]}` : text;
    }
    case "fact.area":
      return fill(m["fact.area"], { area: num(p.area_m2, locale) });
    case "fact.rooms":
      return fill(m["fact.rooms"], {
        bedrooms: p.bedrooms == null ? "—" : num(p.bedrooms, locale),
        bathrooms: p.bathrooms == null ? "—" : num(p.bathrooms, locale),
      });
    case "fact.year_built":
      return fill(m["fact.year_built"], { year: String(p.year) });
    case "fact.location_precision":
      return m[`fact.location.${String(p.precision)}` as keyof Messages] ?? "";
    case "fact.verified":
      return fill(m["fact.verified"], { date: String(p.date) });
    case "fact.ownership_declared":
      return fill(m["fact.ownership_declared"], {
        document:
          (dict.listing.ownership as Record<string, string>)[String(p.document)] ??
          String(p.document),
      });
    case "fact.listed_for":
      return fill(m["fact.listed_for"], { days: num(p.days, locale) });
    case "fact.completeness":
      return fill(m["fact.completeness"], {
        score: String(p.score),
        photos: num(p.photos, locale),
      });
    case "estimate.price_range": {
      const range = fill(m["estimate.price_range"], {
        low: money(p.low, p.currency, locale),
        high: money(p.high, p.currency, locale),
        count: num(p.count, locale),
        median: money(p.median_m2, p.currency, locale),
      });
      const position = p.position
        ? m[`estimate.position.${String(p.position)}` as keyof Messages]
        : "";
      return position ? `${range} ${position}` : range;
    }
    case "estimate.price_unavailable":
      return fill(m[`estimate.price_unavailable.${String(p.reason)}` as keyof Messages] ?? "", {
        count: num(p.count, locale),
      });
    case "source.places_within":
      return (
        fill(m["source.places_within"], {
          count: num(p.count, locale),
          category: categories[String(p.category)] ?? String(p.category),
          radius: num(p.radius_m, locale),
        }) + (p.demo ? ` (${m.demoPlaces})` : approx)
      );
    case "source.nearest":
      return (
        fill(m["source.nearest"], {
          category: categories[String(p.category)] ?? String(p.category),
          name: String((locale === "en" && p.name_en) || p.name_ar || ""),
          distance: num(p.distance_m, locale),
        }) + approx
      );
    case "source.development_nearby":
      return fill(m["source.development_nearby"], {
        name: String((locale === "en" && p.name_en) || p.name_ar || ""),
        status:
          (dict.future.statuses as Record<string, string>)[String(p.status)] ?? String(p.status),
        distance: num(p.distance_km, locale),
        date: p.published_on ? String(p.published_on) : dict.future.undated,
      });
    case "estimate.no_places_recorded":
      return fill(m["estimate.no_places_recorded"], { radius: num(p.radius_m, locale) });
    default: {
      const message = m[s.key as keyof Messages];
      return typeof message === "string" ? message : s.key;
    }
  }
}

/** Badge tone for each kind (TrustBadge kinds). */
export function badgeKind(
  kind: Statement["kind"],
): "fact" | "source" | "estimate" | "ai" | "simulation" {
  return kind === "FACT"
    ? "fact"
    : kind === "SOURCE"
      ? "source"
      : kind === "ESTIMATE"
        ? "estimate"
        : kind === "SIMULATION"
          ? "simulation"
          : "ai";
}
