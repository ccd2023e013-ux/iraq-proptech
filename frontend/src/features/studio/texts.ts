import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { formatArea, formatCompactPrice } from "@/lib/format";

import type { Storyboard, Texts } from "./renderer";

/** Localised strings the renderer draws (only facts from the storyboard). */
export function buildTexts(sb: Storyboard, dict: Dictionary, locale: Locale, site: string): Texts {
  const s = dict.studio.t;
  const p = sb.property;
  const en = locale === "en";
  const pick = (ar: string | null, enValue: string | null) => (en && enValue) || ar || "";
  const period =
    p.rent_period && dict.property.perPeriod
      ? ` ${(dict.property.perPeriod as Record<string, string>)[p.rent_period] ?? ""}`
      : "";
  const price = p.price_amount
    ? `${formatCompactPrice(p.price_amount, p.currency, locale) ?? ""}${period}`
    : dict.listing.priceOnRequest;
  const facts = [
    { label: s.price, value: price },
    ...(p.area_m2 ? [{ label: s.area, value: formatArea(p.area_m2, locale) ?? "" }] : []),
    ...(p.bedrooms != null ? [{ label: s.bedrooms, value: String(p.bedrooms) }] : []),
    ...(p.bathrooms != null ? [{ label: s.bathrooms, value: String(p.bathrooms) }] : []),
  ];
  const nearbyScene = sb.scenes.find((x) => x.type === "nearby");
  const categories = dict.nearby.categories as Record<string, string>;
  const nearby = (nearbyScene?.items ?? []).map((item) => ({
    label: `${categories[item.category] ?? item.category} — ${pick(item.name_ar, item.name_en)}`,
    value: `${item.distance_m.toLocaleString(en ? "en-US" : "ar-IQ-u-nu-latn")} ${en ? "m" : "م"}`,
  }));
  const anyDemo = (nearbyScene?.items ?? []).some((i) => i.is_demo);
  return {
    rtl: !en,
    title: pick(p.title_ar, p.title_en),
    place: [pick(p.district_ar, p.district_en), pick(p.city_ar, p.city_en)]
      .filter(Boolean)
      .join(en ? ", " : "، "),
    price,
    facts,
    nearbyTitle: s.nearby,
    nearby,
    nearbySource: anyDemo ? `${s.sourceOsm} · ${s.sourceDemo}` : s.sourceOsm,
    approximate: s.approximate,
    droneNote: s.droneNote,
    ctaTitle: s.cta,
    ctaLine: s.ctaLine.replace("{ref}", p.reference_code),
    site,
    demo: s.demo,
    brand: s.brand,
  };
}
