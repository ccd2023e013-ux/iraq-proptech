"use client";

import Link from "next/link";
import { type MouseEvent, useEffect, useState } from "react";

import type { Dictionary } from "@/i18n";

import { clearCompare, onCompareChange, readCompare, toggleCompare } from "./store";

function useCompare(): string[] {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    setIds(readCompare());
    return onCompareChange(setIds);
  }, []);
  return ids;
}

export function CompareToggle({ id, dict }: { id: string; dict: Dictionary }) {
  const ids = useCompare();
  const on = ids.includes(id);
  function toggle(event: MouseEvent) {
    event.preventDefault(); // inside a card link
    event.stopPropagation();
    toggleCompare(id, ids);
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={on}
      className={`rounded-md border px-2 py-0.5 text-xs font-medium ${on ? "border-brand-600 bg-brand-600 text-white" : "border-sand-200 bg-white/90 text-sand-700"}`}
    >
      {on ? `✓ ${dict.compare.add}` : dict.compare.add}
    </button>
  );
}

/** Sticky bar shown while at least one listing is selected. */
export function CompareBar({ dict }: { dict: Dictionary }) {
  const ids = useCompare();
  if (ids.length === 0) return null;
  const ready = ids.length >= 2;
  return (
    <div
      role="region"
      aria-label={dict.compare.title}
      className="fixed inset-x-0 bottom-0 z-40 border-t border-sand-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur"
    >
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-sand-700 tabular">
          {ids.length} {dict.compare.selected}
          {!ready && <span className="ms-2 text-xs text-sand-500">{dict.compare.needTwo}</span>}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={clearCompare}
            className="rounded-lg px-3 py-1.5 text-sm text-sand-700 hover:bg-sand-100"
          >
            {dict.compare.clear}
          </button>
          {ready && (
            <Link
              href={`/compare?ids=${ids.join(",")}`}
              className="rounded-lg bg-brand-700 px-4 py-1.5 text-sm font-medium text-white"
            >
              {dict.compare.compareNow}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
