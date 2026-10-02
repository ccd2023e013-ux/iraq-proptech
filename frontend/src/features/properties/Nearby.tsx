import Link from "next/link";

import { Card } from "@/components/ui/Card";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { serverApiFetch } from "@/lib/api/server";
import type { PropertyCard as CardType } from "@/types/property";

import { priceLabel } from "./PropertyCard";

interface Poi {
  id: string;
  category: keyof Dictionary["nearby"]["categories"];
  name_ar: string;
  name_en: string | null;
  distance_m: number | null;
  is_demo: boolean;
}

interface NearbyResult {
  radius_m: number;
  approximate: boolean;
  available: boolean;
  by_category: Record<string, Poi[]>;
  total: number;
}

interface NearbyProperties {
  items: CardType[];
  distances_m: Record<string, number>;
}

/** Neighbourhood context from recorded POIs and other public listings. */
export async function Nearby({
  propertyId,
  dict,
  locale,
}: {
  propertyId: string;
  dict: Dictionary;
  locale: Locale;
}) {
  const n = dict.nearby;
  const [pois, props] = await Promise.all([
    serverApiFetch<NearbyResult>(`/api/v1/properties/${propertyId}/nearby`).catch(() => null),
    serverApiFetch<NearbyProperties>(`/api/v1/properties/${propertyId}/nearby-properties`).catch(
      () => null,
    ),
  ]);
  if (!pois) return null;
  const meters = (m: number | null) =>
    m === null
      ? ""
      : `${Math.round(m).toLocaleString(locale === "ar" ? "ar-IQ" : "en-US")} ${n.meters}`;

  return (
    <>
      <Card title={n.title}>
        {!pois.available ? (
          <p className="text-sm text-sand-500">{n.unavailable}</p>
        ) : pois.total === 0 ? (
          <p className="text-sm text-sand-500">{n.none}</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {Object.entries(pois.by_category).map(([category, items]) => (
              <div key={category}>
                <h3 className="mb-1 text-sm font-semibold text-sand-900">
                  {n.categories[category as Poi["category"]] ?? category}
                </h3>
                <ul className="flex flex-col gap-1 text-sm">
                  {items.map((poi) => (
                    <li key={poi.id} className="flex justify-between gap-3">
                      <span>
                        {locale === "en" && poi.name_en ? poi.name_en : poi.name_ar}
                        {poi.is_demo && (
                          <span className="ms-1 text-xs text-warning">({n.demo})</span>
                        )}
                      </span>
                      <span className="text-sand-500 tabular">{meters(poi.distance_m)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
        {pois.available && pois.approximate && (
          <p className="mt-3 text-xs text-sand-500">{n.approximateNote}</p>
        )}
      </Card>
      {props && props.items.length > 0 && (
        <Card title={n.nearbyProperties}>
          <ul className="flex flex-col divide-y divide-sand-100">
            {props.items.map((card) => (
              <li key={card.id}>
                <Link
                  href={`/properties/${card.id}`}
                  className="flex items-center justify-between gap-3 py-2 text-sm hover:text-brand-700"
                >
                  <span className="truncate">
                    {locale === "en" && card.title_en ? card.title_en : card.title_ar}
                  </span>
                  <span className="shrink-0 font-semibold tabular">
                    {priceLabel(card, dict, locale)}
                  </span>
                  <span className="shrink-0 text-xs text-sand-500 tabular">
                    {meters(props.distances_m[card.id] ?? null)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
