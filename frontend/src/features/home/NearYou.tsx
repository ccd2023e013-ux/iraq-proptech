"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { SafeImage } from "@/components/ui/SafeImage";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { priceLabel } from "@/features/properties/PropertyCard";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { placeName } from "@/lib/format";
import type { PropertyCard } from "@/types/property";

type State =
  | { kind: "idle" }
  | { kind: "locating" }
  | { kind: "denied" }
  | { kind: "error" }
  | { kind: "done"; items: PropertyCard[]; lat: number; lon: number };

export const NEAR_RADIUS_KM = 10;

/** The search the "near you" section runs (radius + nearest first). */
export function nearQuery(lat: number, lon: number): string {
  const q = new URLSearchParams({
    near_lat: lat.toFixed(5),
    near_lon: lon.toFixed(5),
    radius_km: String(NEAR_RADIUS_KM),
    sort: "distance",
    page_size: "4",
  });
  return q.toString();
}

/**
 * "Properties near you": asks for the location only when the visitor presses
 * the button (never on page load), and the position is used for this one
 * search only — it is not stored.
 */
export function NearYou({ dict, locale }: { dict: Dictionary; locale: Locale }) {
  const h = dict.homeV2;
  const [state, setState] = useState<State>({ kind: "idle" });

  function locate() {
    if (!("geolocation" in navigator)) {
      setState({ kind: "denied" });
      return;
    }
    setState({ kind: "locating" });
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const result = await apiFetch<{ items: PropertyCard[] }>(
            `/api/v1/search/properties?${nearQuery(coords.latitude, coords.longitude)}`,
          );
          setState({
            kind: "done",
            items: result.items,
            lat: coords.latitude,
            lon: coords.longitude,
          });
        } catch {
          setState({ kind: "error" });
        }
      },
      () => setState({ kind: "denied" }),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
    );
  }

  return (
    <section
      aria-labelledby="near-heading"
      className="rule-top grid grid-cols-1 gap-8 pt-10 md:grid-cols-12 md:gap-6 md:pt-12"
    >
      <div className="flex min-w-0 flex-col items-start gap-3 md:col-span-4 lg:col-span-3">
        <h2 id="near-heading" className="display-md text-ink">
          {h.nearTitle}
        </h2>
        <p className="text-ink-2">{h.nearBody}</p>
        {state.kind !== "done" && (
          <Button
            variant="secondary"
            onClick={locate}
            loading={state.kind === "locating"}
            data-testid="near-you"
          >
            {h.nearButton}
          </Button>
        )}
        {state.kind === "denied" && <p className="text-sm text-ink-3">{dict.map.nearMeDenied}</p>}
        {state.kind === "error" && <p className="text-sm text-danger">{dict.map.error}</p>}
      </div>
      <div className="min-w-0 md:col-span-8 lg:col-span-9">
        {state.kind === "done" && state.items.length === 0 && (
          <p className="rounded-[var(--radius-card)] bg-fill px-5 py-8 text-ink-2">
            {h.nearNone.replace("{km}", String(NEAR_RADIUS_KM))}
          </p>
        )}
        {state.kind === "done" && state.items.length > 0 && (
          <div className="flex flex-col gap-4">
            <ul className="grid grid-cols-2 gap-x-4 gap-y-6 lg:grid-cols-4">
              {state.items.map((card) => {
                const title = locale === "en" && card.title_en ? card.title_en : card.title_ar;
                return (
                  <li key={card.id}>
                    <Link href={`/properties/${card.id}`} className="group flex flex-col gap-2">
                      <div className="relative aspect-[4/3] overflow-hidden rounded-[var(--radius-card)] bg-fill">
                        {card.cover_url && (
                          <SafeImage
                            src={card.cover_url}
                            alt=""
                            fallbackLabel="—"
                            className="size-full object-cover transition duration-[var(--duration-slow)] group-hover:scale-[1.03]"
                          />
                        )}
                        {card.is_demo && (
                          <span className="absolute start-2 bottom-2">
                            <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>
                          </span>
                        )}
                      </div>
                      <span className="font-semibold text-ink tabular">
                        {priceLabel(card, dict, locale)}
                      </span>
                      <span className="line-clamp-1 text-sm text-ink-2">{title}</span>
                      <span className="text-xs text-ink-3">{placeName(card.city, locale)}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
            <Link
              href={`/map?near_lat=${state.lat.toFixed(5)}&near_lon=${state.lon.toFixed(5)}&radius_km=${NEAR_RADIUS_KM}`}
              className="self-start text-sm font-medium text-accent underline-offset-4 hover:underline"
            >
              {h.nearOnMap}
            </Link>
          </div>
        )}
      </div>
    </section>
  );
}
