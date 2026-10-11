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
  const facts: Fact[] = [];
  if (card.bedrooms !== null)
    facts.push({ icon: "bed", text: String(card.bedrooms), label: dict.listing.bedrooms });
  if (card.bathrooms !== null)
    facts.push({ icon: "bath", text: String(card.bathrooms), label: dict.listing.bathrooms });
  const area = formatArea(card.area_m2, locale);
  if (area) facts.push({ icon: "area", text: area });

  // Survey card: the photograph is the figure; everything else sits on the
  // page as type. Only the save control floats on the image, and DEMO is a
  // gold tag on the image's bottom edge (where trust labels always live).
  return (
    <article className="group relative flex flex-col gap-3">
      <Link
        href={`/properties/${card.id}`}
        className="absolute inset-0 z-10 rounded-[var(--radius-card)]"
        aria-label={title}
      />
      <div className="relative aspect-[4/3] overflow-hidden rounded-[var(--radius-card)] bg-fill shadow-[inset_0_0_0_1px_var(--hairline)]">
        {card.cover_url ? (
          <SafeImage
            src={card.cover_url}
            alt=""
            fallbackLabel={dict.listing.noImage}
            className="size-full object-cover transition-transform duration-[var(--duration-slow)] ease-[var(--ease-standard)] group-hover:scale-[1.02]"
          />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-2 text-[13px] text-ink-3">
            <Icon name="home" className="size-6 opacity-70" />
            {dict.listing.noImage}
          </div>
        )}
        {(card.is_demo || card.is_featured) && (
          <div className="absolute start-0 bottom-0 flex">
            {card.is_demo && (
              <span className="rounded-se-[var(--radius-tag)] bg-gold-500 px-2 py-0.5 text-[11px] font-semibold text-[#1d1405]">
                {dict.listing.demo}
                {card.cover_url && (
                  <span className="font-medium"> · {dict.listing.representativePhoto}</span>
                )}
              </span>
            )}
            {card.is_featured && (
              <span className="bg-canvas/80 px-2 py-0.5 text-[11px] font-medium text-ink backdrop-blur-md">
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
      <div className="flex flex-col gap-0.5">
        <div className="flex items-baseline justify-between gap-3">
          <p className={`kpi text-ink ${compact ? "text-base" : "text-xl"}`}>
            {priceLabel(card, dict, locale)}
          </p>
          <span className="caption shrink-0">
            {dict.listing.purposes[card.purpose]}
            {card.verified && (
              <span className="ms-2 inline-flex items-center gap-1 text-accent">
                <Icon name="check" className="size-3.5" strokeWidth={2.2} />
                {dict.listing.verified}
              </span>
            )}
          </span>
        </div>
        <h3
          className={`line-clamp-1 text-ink-2 transition-colors group-hover:text-ink ${compact ? "text-sm" : "text-[15px]"}`}
        >
          {title}
        </h3>
        {!compact && (
          <p className="meta flex min-w-0 items-center gap-x-3 tabular">
            <span className="truncate">{[typeName, where].filter(Boolean).join(" · ")}</span>
            {facts.length > 0 && (
              <span className="flex shrink-0 items-center gap-2.5">
                {facts.map((f) => (
                  <span key={f.icon} className="flex items-center gap-1">
                    <Icon name={f.icon} className="size-3.5 text-ink-3" strokeWidth={1.8} />
                    {f.text}
                    {f.label && <span className="sr-only">{f.label}</span>}
                  </span>
                ))}
              </span>
            )}
          </p>
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
