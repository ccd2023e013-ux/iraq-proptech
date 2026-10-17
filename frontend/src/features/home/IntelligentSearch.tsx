"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import type { Dictionary } from "@/i18n";
import { toApiQuery } from "@/lib/search";

export interface SearchOption {
  value: string;
  label: string;
}

const PURPOSES = ["SALE", "RENT"] as const;

/** Builds the destination for the hero search (exported for tests). */
export function searchDestination(input: {
  ai: boolean;
  q: string;
  purpose: string;
  cityId: string;
  type: string;
}): string {
  if (input.ai) {
    const q = input.q.trim();
    return q ? `/search/smart?q=${encodeURIComponent(q)}` : "/search/smart";
  }
  const query = toApiQuery({
    q: input.q.trim(),
    purpose: input.purpose,
    city_id: input.cityId,
    property_types: input.type,
  });
  return query ? `/properties?${query}` : "/properties";
}

/**
 * The plate's query: one large field, then purpose, place and type, and the
 * action. "Describe it in your words" hands the sentence to /search/smart
 * (the MAKAN assistant), which labels how each answer was produced.
 * Flat: it is docked in the home console, not floated over the map.
 */
export function IntelligentSearch({
  dict,
  cities,
  types,
  defaultCity = "",
}: {
  dict: Dictionary;
  cities: SearchOption[];
  types: SearchOption[];
  /** The plate's place (e.g. Basra on the home page). */
  defaultCity?: string;
}) {
  const h = dict.homeV2;
  const router = useRouter();
  const [ai, setAi] = useState(false);
  const [q, setQ] = useState("");
  const [purpose, setPurpose] = useState<string>("SALE");
  const [cityId, setCityId] = useState(defaultCity);
  const [type, setType] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    router.push(searchDestination({ ai, q, purpose, cityId, type }));
  }

  const select = "field h-10 min-w-0 bg-fill text-[15px] shadow-none";

  return (
    <form onSubmit={onSubmit} role="search" className="flex w-full flex-col gap-3">
      <div className="flex items-stretch gap-2">
        <label className="relative block min-w-0 flex-1">
          <span className="sr-only">{ai ? h.aiPlaceholder : h.searchPlaceholder}</span>
          <Icon
            name={ai ? "sparkle" : "search"}
            className="pointer-events-none absolute start-4 top-1/2 size-5 -translate-y-1/2 text-ink-3"
          />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={ai ? h.aiPlaceholder : h.searchPlaceholder}
            className="field h-13 bg-fill ps-12 text-[1.0625rem] shadow-none"
          />
        </label>
        <button type="submit" className="btn btn-primary h-13 shrink-0 px-5">
          <Icon name="search" className="size-[18px] sm:hidden" strokeWidth={2} />
          <span className="max-sm:sr-only">{h.search}</span>
        </button>
      </div>
      <div className="grid grid-cols-2 items-center gap-2 sm:grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)]">
        <div
          role="radiogroup"
          aria-label={dict.property.purpose}
          className={`seg col-span-2 w-fit transition-opacity duration-[var(--duration-base)] sm:col-span-1 ${ai ? "pointer-events-none opacity-40" : ""}`}
        >
          {PURPOSES.map((p) => (
            <button
              key={p}
              type="button"
              role="radio"
              aria-checked={purpose === p}
              onClick={() => setPurpose(p)}
            >
              {dict.listing.purposes[p]}
            </button>
          ))}
        </div>
        {!ai && (
          <>
            <select
              aria-label={h.anyCity}
              value={cityId}
              onChange={(e) => setCityId(e.target.value)}
              className={select}
            >
              <option value="">{h.anyCity}</option>
              {cities.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
            <select
              aria-label={h.anyType}
              value={type}
              onChange={(e) => setType(e.target.value)}
              className={select}
            >
              <option value="">{h.anyType}</option>
              {types.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </>
        )}
      </div>
      <label className="flex w-fit cursor-pointer items-center gap-2.5 text-sm text-ink-2 hover:text-ink">
        <input
          type="checkbox"
          checked={ai}
          onChange={(e) => setAi(e.target.checked)}
          className="peer sr-only"
        />
        <span
          aria-hidden
          className="relative h-5 w-9 shrink-0 rounded-full bg-fill-strong transition peer-checked:bg-accent-fill peer-focus-visible:ring-2 peer-focus-visible:ring-accent after:absolute after:top-0.5 after:start-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4"
        />
        {h.aiToggle}
      </label>
    </form>
  );
}
