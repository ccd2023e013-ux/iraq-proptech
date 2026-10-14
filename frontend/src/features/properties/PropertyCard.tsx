import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { SafeImage } from "@/components/ui/SafeImage";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { formatArea, formatCompactPrice, placeName } from "@/lib/format";
import type { PropertyCard as Card } from "@/types/property";

import { CompareToggle } from "@/features/compare/CompareControls";

import { FavoriteButton } from "./FavoriteButton";

interface Fact {
  icon: "bed" | "bath" | "area";
  text: string;
  /** Spoken label for screen readers (the icon carries it visually). */
  label?: string;
}

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
  feature = false,
}: {
  card: Card;
  dict: Dictionary;
  locale: Locale;
  typeName?: string;
  favorite?: boolean;
  signedIn: boolean;
  /** Smaller tile for dense editorial layouts (no facts row). */
  compact?: boolean;
  /** Lead tile in an editorial layout: wider photograph on large screens. */
  feature?: boolean;
}) {
  const title = locale === "en" && card.title_en ? card.title_en : card.title_ar;
  const where = [
    placeName(card.neighborhood ?? card.district, locale),
    placeName(card.city, locale),
  ]
    .filter(Boolean)
    .join("، ");
  const facts: Fact[] = [];
  if (card.bedrooms !== null)
    facts.push({ icon: "bed", text: String(card.bedrooms), label: dict.listing.bedrooms });
  if (card.bathrooms !== null)
    facts.push({ icon: "bath", text: String(card.bathrooms), label: dict.listing.bathrooms });
  const area = formatArea(card.area_m2, locale);
  if (area) facts.push({ icon: "area", text: area });

  // The photograph is the figure; everything else is type on the page.
  // Only the save control floats on the image, and DEMO sits on the image's
  // bottom edge (where trust labels always live).
  return (
    <article className="group relative flex flex-col gap-4">
      <Link
        href={`/properties/${card.id}`}
        className="absolute inset-0 z-10 rounded-[var(--radius-card)]"
        aria-label={title}
      />
      <div
        className={`relative ${feature ? "aspect-[4/3] lg:aspect-[16/9]" : "aspect-[4/3]"} overflow-hidden rounded-[var(--radius-media)] bg-fill shadow-[inset_0_0_0_1px_var(--hairline)]`}
      >
        {card.cover_url ? (
          <SafeImage
            src={card.cover_url}
            alt=""
            fallbackLabel={dict.listing.noImage}
            className="photo size-full object-cover transition-transform duration-[var(--duration-slow)] ease-[var(--ease-standard)] group-hover:scale-[1.025]"
          />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-2 text-sm text-ink-3">
            <Icon name="home" className="size-6 opacity-70" />
            {dict.listing.noImage}
          </div>
        )}
        {(card.is_demo || card.is_featured) && (
          <div className="absolute start-0 bottom-0 flex">
            {card.is_demo && (
              <span className="flex items-center gap-1.5 rounded-se-[var(--radius-tag)] bg-gold-500 px-2.5 py-1 text-xs font-semibold text-[#1d1405]">
                {dict.listing.demo}
                {card.cover_url && !compact && (
                  <span className="font-medium opacity-80">{dict.listing.representativePhoto}</span>
                )}
              </span>
            )}
            {card.is_featured && (
              <span className="bg-canvas/80 px-2.5 py-1 text-xs font-medium text-ink backdrop-blur-md">
                {dict.listing.promoted}
              </span>
            )}
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
      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <p className={`kpi text-ink ${compact ? "text-xl" : "text-[1.625rem]"}`}>
            {priceLabel(card, dict, locale)}
          </p>
          <span className="meta shrink-0">{dict.listing.purposes[card.purpose]}</span>
        </div>
        <h3
          className={`line-clamp-1 text-ink transition-colors group-hover:text-accent ${compact ? "text-[15px]" : "text-base font-medium"}`}
        >
          {title}
        </h3>
        {(where || typeName) && (
          <p className="meta flex min-w-0 items-center gap-1.5">
            <Icon name="pin" className="size-4 shrink-0 text-spatial" strokeWidth={1.7} />
            <span className="truncate">{where || typeName}</span>
          </p>
        )}
        {!compact && (facts.length > 0 || card.verified) && (
          <ul className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2 tabular">
            {typeName && <li>{typeName}</li>}
            {facts.map((f) => (
              <li key={f.icon} className="flex items-center gap-1.5">
                <Icon name={f.icon} className="size-4 text-ink-3" strokeWidth={1.7} />
                {f.text}
                {f.label && <span className="sr-only">{f.label}</span>}
              </li>
            ))}
            {card.verified && (
              <li className="flex items-center gap-1 text-accent">
                <Icon name="check" className="size-4" strokeWidth={2} />
                {dict.listing.verified}
              </li>
            )}
          </ul>
        )}
        {!compact && (
          <div className="relative z-20 mt-2 flex items-center justify-between gap-3">
            <span className="caption min-w-0 truncate">{card.agency_name}</span>
            <CompareToggle id={card.id} dict={dict} />
          </div>
        )}
      </div>
    </article>
  );
}
