"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import type { Dictionary } from "@/i18n";
import { toApiQuery } from "@/lib/search";

const PURPOSES = ["SALE", "RENT"] as const;

/** Landing-page search: keyword + sale/rent, then hands off to /properties. */
export function HeroSearch({ dict }: { dict: Dictionary }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [purpose, setPurpose] = useState<string>("SALE");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const query = toApiQuery({ q: q.trim(), purpose });
    router.push(query ? `/properties?${query}` : "/properties");
  }

  return (
    <form
      onSubmit={onSubmit}
      role="search"
      className="flex w-full max-w-2xl flex-col gap-3 rounded-[var(--radius-card)] bg-white p-3 text-sand-900 shadow-lg"
    >
      <div className="flex gap-1" role="radiogroup" aria-label={dict.property.purpose}>
        {PURPOSES.map((p) => (
          <button
            key={p}
            type="button"
            role="radio"
            aria-checked={purpose === p}
            onClick={() => setPurpose(p)}
            className={`rounded-lg px-4 py-1.5 text-sm font-medium ${purpose === p ? "bg-brand-700 text-white" : "text-sand-700 hover:bg-sand-100"}`}
          >
            {dict.listing.purposes[p]}
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={dict.search.keyword}
          aria-label={dict.search.keyword}
          className="h-12 min-w-0 flex-1 rounded-lg border border-sand-200 px-4"
        />
        <button
          type="submit"
          className="h-12 rounded-lg bg-gold-500 px-6 font-semibold text-brand-900 hover:bg-gold-300"
        >
          {dict.landing.heroCta}
        </button>
      </div>
    </form>
  );
}
