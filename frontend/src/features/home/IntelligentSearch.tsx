"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

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

  const select =
    "h-11 min-w-0 rounded-full bg-fill px-4 text-sm text-ink outline-none ring-accent transition focus-visible:ring-2";

  return (
    <form
      onSubmit={onSubmit}
      role="search"
      className="w-full rounded-[var(--radius-media)] bg-glass p-2 shadow-float ring-1 ring-hairline backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 pt-1 pb-2">
        <div
          role="radiogroup"
          aria-label={dict.property.purpose}
          className={`flex rounded-full bg-fill p-1 transition ${ai ? "pointer-events-none opacity-40" : ""}`}
        >
          {PURPOSES.map((p) => (
            <button
              key={p}
              type="button"
              role="radio"
              aria-checked={purpose === p}
              onClick={() => setPurpose(p)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition duration-[var(--duration-quick)] ${purpose === p ? "bg-surface text-ink shadow-soft" : "text-ink-2 hover:text-ink"}`}
            >
              {dict.listing.purposes[p]}
            </button>
          ))}
        </div>
        <label className="flex cursor-pointer items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium text-ink-2 hover:bg-fill">
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
      <div className="flex flex-col gap-2 sm:flex-row">
        {!ai && (
          <div className="grid grid-cols-2 gap-2 sm:flex">
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
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={ai ? h.aiPlaceholder : h.searchPlaceholder}
          aria-label={ai ? h.aiPlaceholder : h.searchPlaceholder}
          className="h-11 min-w-0 flex-1 rounded-full bg-fill px-4 text-ink outline-none ring-accent transition placeholder:text-ink-3 focus-visible:ring-2"
        />
        <button
          type="submit"
          className="h-11 rounded-full bg-accent-fill px-6 font-medium text-on-accent shadow-soft transition hover:bg-accent-fill-hover active:scale-[0.98]"
        >
          {h.search}
        </button>
      </div>
    </form>
  );
}
