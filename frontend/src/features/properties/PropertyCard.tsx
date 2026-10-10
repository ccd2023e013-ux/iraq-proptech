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

  // Editorial card: the photograph carries the card; text sits on the page,
  // not in a box. Price leads, then title, then quiet facts with icons.
  return (
    <article className="group relative flex flex-col gap-3.5">
      <Link
        href={`/properties/${card.id}`}
        className="absolute inset-0 z-10 rounded-[var(--radius-card)]"
        aria-label={title}
      />
      <div className="relative aspect-[4/3] overflow-hidden rounded-[var(--radius-card)] bg-fill shadow-[inset_0_0_0_1px_var(--hairline)] transition-[box-shadow,translate] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] group-hover:-translate-y-0.5 group-hover:shadow-[var(--shadow-float)]">
        {card.cover_url ? (
          <SafeImage
            src={card.cover_url}
            alt=""
            fallbackLabel={dict.listing.noImage}
            className="size-full object-cover transition-transform duration-[900ms] ease-[var(--ease-out-soft)] group-hover:scale-[1.045]"
          />
        ) : (
          <div className="relative isolate flex size-full flex-col items-center justify-center gap-2 text-[13px] text-ink-3">
            <div aria-hidden className="stage-grid absolute inset-0 -z-10 opacity-80" />
            <Icon name="home" className="size-6 text-ink-3/80" />
            {dict.listing.noImage}
          </div>
        )}
        {/* A soft shade at the top keeps chips legible on bright photos. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-black/25 to-transparent"
        />
        <div className="absolute start-3 top-3 flex flex-wrap gap-1.5">
          <span className="surface-float rounded-full px-2.5 py-0.5 text-xs font-medium text-ink">
            {dict.listing.purposes[card.purpose]}
          </span>
          {card.verified && !compact && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-fill px-2.5 py-0.5 text-xs font-medium text-on-accent">
              <Icon name="check" className="size-3.5" strokeWidth={2.2} />
              {dict.listing.verified}
            </span>
          )}
        </div>
        <div className="absolute bottom-3 start-3 flex flex-wrap gap-1.5">
          {card.verified && compact && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-fill px-2 py-0.5 text-[11px] font-medium text-on-accent">
              <Icon name="check" className="size-3" strokeWidth={2.4} />
              {dict.listing.verified}
            </span>
          )}
          {card.is_demo && (
            <span className="rounded-full bg-gold-500 px-2 py-0.5 text-[11px] font-semibold text-[#1d1405]">
              {dict.listing.demo}
            </span>
          )}
          {card.is_featured && (
            <span className="surface-float rounded-full px-2 py-0.5 text-[11px] font-medium text-ink">
              {dict.listing.promoted}
            </span>
          )}
        </div>
        {!compact && (
          <div className="absolute end-3 bottom-3 z-20 opacity-0 transition-opacity duration-[var(--duration-base)] group-focus-within:opacity-100 group-hover:opacity-100 max-md:opacity-100">
            <CompareToggle id={card.id} dict={dict} />
          </div>
        )}
        <div className="absolute end-3 top-3 z-20">
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
      <div className="flex flex-col gap-1 px-0.5">
        <p
          className={`font-display font-semibold tracking-tight text-ink tabular ${compact ? "text-base" : "text-[19px] leading-snug"}`}
        >
          {priceLabel(card, dict, locale)}
        </p>
        <h3 className={`line-clamp-1 text-ink-2 ${compact ? "text-sm" : "text-[15px]"}`}>
          {title}
        </h3>
        {!compact && (where || typeName) && (
          <p className="flex min-w-0 items-center gap-1.5 text-[13px] text-ink-3">
            <Icon name="pin" className="size-3.5 shrink-0 text-spatial" />
            <span className="truncate">{[typeName, where].filter(Boolean).join(" · ")}</span>
          </p>
        )}
        {!compact && facts.length > 0 && (
          <ul className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-ink-2 tabular">
            {facts.map((f) => (
              <li key={f.icon} className="flex items-center gap-1.5">
                <Icon name={f.icon} className="size-4 text-ink-3" />
                <span>{f.text}</span>
                {f.label && <span className="sr-only">{f.label}</span>}
              </li>
            ))}
          </ul>
        )}
        {!compact && card.agency_name && <p className="meta mt-0.5">{card.agency_name}</p>}
      </div>
    </article>
  );
}
