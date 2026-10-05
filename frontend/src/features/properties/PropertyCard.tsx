import Link from "next/link";

import { SafeImage } from "@/components/ui/SafeImage";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { formatArea, formatCompactPrice, placeName } from "@/lib/format";
import type { PropertyCard as Card } from "@/types/property";

import { CompareToggle } from "@/features/compare/CompareControls";

import { FavoriteButton } from "./FavoriteButton";

export function priceLabel(card: Card, dict: Dictionary, locale: Locale): string {
  if (card.price_on_request || card.price_amount === null) return dict.listing.priceOnRequest;
  const price = formatCompactPrice(card.price_amount, card.currency, locale) ?? "";
  const period = card.rent_period ? ` ${dict.property.perPeriod[card.rent_period]}` : "";
  return `${price}${period}`;
}

export function PropertyCard({
  card,
  dict,
  locale,
  typeName,
  favorite,
  signedIn,
  compact = false,
}: {
  card: Card;
  dict: Dictionary;
  locale: Locale;
  typeName?: string;
  favorite?: boolean;
  signedIn: boolean;
  /** Smaller tile for dense editorial layouts (no facts row). */
  compact?: boolean;
}) {
  const title = locale === "en" && card.title_en ? card.title_en : card.title_ar;
  const where = [
    placeName(card.neighborhood ?? card.district, locale),
    placeName(card.city, locale),
  ]
    .filter(Boolean)
    .join("، ");
  const facts = [
    card.bedrooms !== null ? `${card.bedrooms} ${dict.listing.bedrooms}` : null,
    card.bathrooms !== null ? `${card.bathrooms} ${dict.listing.bathrooms}` : null,
    formatArea(card.area_m2, locale),
  ].filter(Boolean);

  return (
    <article className="group relative flex flex-col gap-3">
      <Link href={`/properties/${card.id}`} className="absolute inset-0 z-10" aria-label={title} />
      <div className="relative aspect-[4/3] overflow-hidden rounded-[var(--radius-card)] bg-fill">
        {card.cover_url ? (
          <SafeImage
            src={card.cover_url}
            alt=""
            fallbackLabel={dict.listing.noImage}
            className="size-full object-cover transition duration-[var(--duration-slow)] ease-[var(--ease-out-soft)] group-hover:scale-[1.03]"
          />
        ) : (
          <div className="grid size-full place-items-center text-sm text-ink-3">
            {dict.listing.noImage}
          </div>
        )}
        <div className="absolute start-2.5 top-2.5 flex flex-wrap gap-1.5">
          <span className="rounded-full bg-glass px-2.5 py-0.5 text-xs font-medium text-ink backdrop-blur-md">
            {dict.listing.purposes[card.purpose]}
          </span>
          {card.verified && (
            <span className="rounded-full bg-success px-2.5 py-0.5 text-xs font-medium text-white">
              ✓ {dict.listing.verified}
            </span>
          )}
        </div>
        <div className="absolute bottom-2.5 start-2.5 flex flex-wrap gap-1.5">
          {card.is_demo && (
            <span className="rounded-full bg-gold-500 px-2 py-0.5 text-[11px] font-semibold text-white">
              {dict.listing.demo}
            </span>
          )}
          {card.is_featured && (
            <span className="rounded-full bg-glass px-2 py-0.5 text-[11px] font-medium text-ink backdrop-blur-md">
              {dict.listing.promoted}
            </span>
          )}
        </div>
        {!compact && (
          <div className="absolute end-2.5 bottom-2.5 z-20 opacity-90 transition group-hover:opacity-100">
            <CompareToggle id={card.id} dict={dict} />
          </div>
        )}
        <div className="absolute end-2.5 top-2.5 z-20">
          <FavoriteButton
            propertyId={card.id}
            initial={!!favorite}
            signedIn={signedIn}
            labels={{
              save: dict.property.save,
              saved: dict.property.saved,
              loginToSave: dict.property.loginToSave,
            }}
          />
        </div>
      </div>
      <div className="flex flex-col gap-0.5 px-0.5">
        <p
          className={`font-display font-semibold text-ink tabular ${compact ? "text-base" : "text-lg"}`}
        >
          {priceLabel(card, dict, locale)}
        </p>
        <h3 className={`line-clamp-1 text-ink-2 ${compact ? "text-sm" : ""}`}>{title}</h3>
        {!compact && (
          <p className="text-sm text-ink-3">{[typeName, where].filter(Boolean).join(" · ")}</p>
        )}
        {!compact && facts.length > 0 && (
          <p className="text-sm text-ink-3 tabular">{facts.join(" · ")}</p>
        )}
        {!compact && card.agency_name && <p className="text-xs text-ink-3">{card.agency_name}</p>}
      </div>
    </article>
  );
}
