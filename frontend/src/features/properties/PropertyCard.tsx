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
}: {
  card: Card;
  dict: Dictionary;
  locale: Locale;
  typeName?: string;
  favorite?: boolean;
  signedIn: boolean;
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
    <article className="group relative flex flex-col overflow-hidden rounded-[var(--radius-card)] border border-sand-200 bg-white shadow-sm transition hover:shadow-md">
      <Link href={`/properties/${card.id}`} className="absolute inset-0 z-10" aria-label={title} />
      <div className="relative aspect-[4/3] bg-sand-100">
        {card.cover_url ? (
          <SafeImage
            src={card.cover_url}
            alt=""
            fallbackLabel={dict.listing.noImage}
            className="size-full object-cover transition group-hover:scale-[1.02]"
          />
        ) : (
          <div className="grid size-full place-items-center text-sm text-sand-500">
            {dict.listing.noImage}
          </div>
        )}
        <div className="absolute start-2 top-2 flex flex-wrap gap-1.5">
          <span className="rounded-md bg-brand-800/90 px-2 py-0.5 text-xs font-medium text-white">
            {dict.listing.purposes[card.purpose]}
          </span>
          {card.verified && (
            <span className="rounded-md bg-success px-2 py-0.5 text-xs font-medium text-white">
              ✓ {dict.listing.verified}
            </span>
          )}
          {card.is_featured && (
            <span className="rounded-md bg-brand-700 px-2 py-0.5 text-xs font-bold text-white">
              {dict.listing.promoted}
            </span>
          )}
          {card.is_demo && (
            <span className="rounded-md bg-gold-500 px-2 py-0.5 text-xs font-bold text-white">
              {dict.listing.demo}
            </span>
          )}
        </div>
        <div className="absolute bottom-2 start-2 z-20">
          <CompareToggle id={card.id} dict={dict} />
        </div>
        <div className="absolute end-2 top-2 z-20">
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
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <p className="text-lg font-bold text-brand-900 tabular">{priceLabel(card, dict, locale)}</p>
        <h3 className="line-clamp-2 font-semibold text-sand-900">{title}</h3>
        <p className="text-sm text-sand-500">{[typeName, where].filter(Boolean).join(" · ")}</p>
        {facts.length > 0 && (
          <p className="mt-auto pt-2 text-sm text-sand-700 tabular">{facts.join(" · ")}</p>
        )}
        {card.agency_name && <p className="text-xs text-sand-500">{card.agency_name}</p>}
      </div>
    </article>
  );
}
