import Link from "next/link";

import { SafeImage } from "@/components/ui/SafeImage";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { placeName } from "@/lib/format";
import type { PropertyCard as Card } from "@/types/property";

import { PlacePlate } from "./PlacePlate";
import { priceLabel } from "./PropertyCard";

/**
 * A listing as one line of a plate's ledger: photo (or place plate), the price
 * as a measurement, then what and where. Used in docked consoles.
 */
export function ListingRow({
  card,
  dict,
  locale,
  photo,
  typeName,
}: {
  card: Card;
  dict: Dictionary;
  locale: Locale;
  /** This view's photo for the listing (null: place plate). */
  photo: string | null;
  typeName?: string;
}) {
  const title = locale === "en" && card.title_en ? card.title_en : card.title_ar;
  const where =
    placeName(card.neighborhood ?? card.district, locale) || placeName(card.city, locale);
  return (
    <Link
      href={`/properties/${card.id}`}
      className="group flex items-center gap-4 py-3 transition-colors"
    >
      <span className="relative size-16 shrink-0 overflow-hidden rounded-[var(--radius-control)] bg-fill">
        {photo ? (
          <SafeImage src={photo} alt="" fallbackLabel="" className="photo size-full object-cover" />
        ) : (
          <PlacePlate type={card.property_type_code} size="sm" />
        )}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-baseline justify-between gap-3">
          <span className="kpi text-lg text-ink transition-colors group-hover:text-accent">
            {priceLabel(card, dict, locale)}
          </span>
          <span className="caption shrink-0">{dict.listing.purposes[card.purpose]}</span>
        </span>
        <span className="truncate text-[15px] text-ink-2">{title}</span>
        <span className="caption flex items-center gap-2">
          <span className="truncate">
            {[typeName, where].filter(Boolean).join(locale === "ar" ? "، " : ", ")}
          </span>
          {card.is_demo && (
            <span className="shrink-0 font-medium text-gold-700">{dict.listing.demo}</span>
          )}
        </span>
      </span>
    </Link>
  );
}
