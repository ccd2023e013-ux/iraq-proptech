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
 * One instrument for both kinds of search: structured (purpose, city, type,
 * keyword) or natural language ("AI search"), which hands off to /search/smart.
 */
export function IntelligentSearch({
  dict,
  cities,
  types,
}: {
  dict: Dictionary;
  cities: SearchOption[];
  types: SearchOption[];
}) {
  const h = dict.homeV2;
  const router = useRouter();
  const [ai, setAi] = useState(false);
  const [q, setQ] = useState("");
  const [purpose, setPurpose] = useState<string>("SALE");
  const [cityId, setCityId] = useState("");
  const [type, setType] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    router.push(searchDestination({ ai, q, purpose, cityId, type }));
  }

  const select = "field min-w-0 bg-fill shadow-none";

  return (
    <form
      onSubmit={onSubmit}
      role="search"
      className="surface-float flex w-full flex-col gap-2 rounded-[var(--radius-card)] p-2.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-0.5 pb-1">
        <div
          role="radiogroup"
          aria-label={dict.property.purpose}
          className={`seg transition-opacity duration-[var(--duration-base)] ${ai ? "pointer-events-none opacity-40" : ""}`}
        >
          {PURPOSES.map((p) => (
            <button
              key={p}
              type="button"
              role="radio"
              aria-checked={purpose === p}
              onClick={() => setPurpose(p)}
              className="hover:text-ink"
            >
              {dict.listing.purposes[p]}
            </button>
          ))}
        </div>
        <label className="flex cursor-pointer items-center gap-2 rounded-[var(--radius-control)] px-3 py-1.5 text-sm font-medium text-ink-2 hover:bg-fill">
          <input
            type="checkbox"
            checked={ai}
            onChange={(e) => setAi(e.target.checked)}
            className="peer sr-only"
          />
          <span
            aria-hidden
            className="relative h-5 w-9 rounded-full bg-fill-strong transition peer-checked:bg-accent-fill peer-focus-visible:ring-2 peer-focus-visible:ring-accent after:absolute after:top-0.5 after:start-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4"
          />
          {h.aiToggle}
        </label>
      </div>
      {/* The question first, large; then the place and type, and the action. */}
      <label className="relative block">
        <span className="sr-only">{ai ? h.aiPlaceholder : h.searchPlaceholder}</span>
        <Icon
          name={ai ? "insight" : "search"}
          className="pointer-events-none absolute start-4 top-1/2 size-5 -translate-y-1/2 text-ink-3"
        />
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={ai ? h.aiPlaceholder : h.searchPlaceholder}
          className="field h-14 bg-fill ps-12 text-[1.0625rem] shadow-none"
        />
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        {!ai && (
          <div className="grid flex-1 grid-cols-2 gap-2">
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
          </div>
        )}
        <button type="submit" className={`btn btn-primary h-12 px-6 ${ai ? "flex-1" : ""}`}>
          <Icon name="search" className="size-[18px]" strokeWidth={2} />
          {h.search}
        </button>
      </div>
    </form>
  );
}
