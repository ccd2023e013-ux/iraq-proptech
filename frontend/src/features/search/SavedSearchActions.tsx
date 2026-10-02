"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";

const FREQUENCIES = ["NONE", "INSTANT", "DAILY", "WEEKLY"] as const;

export function SavedSearchActions({
  dict,
  id,
  frequency,
}: {
  dict: Dictionary;
  id: string;
  frequency: (typeof FREQUENCIES)[number];
}) {
  const router = useRouter();
  const s = dict.savedSearches;
  const [value, setValue] = useState(frequency);
  const [busy, setBusy] = useState(false);

  async function change(next: (typeof FREQUENCIES)[number]) {
    setValue(next);
    setBusy(true);
    try {
      await apiFetch(`/api/v1/me/saved-searches/${id}`, {
        method: "PATCH",
        body: { alert_frequency: next },
      });
    } catch {
      setValue(frequency);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await apiFetch(`/api/v1/me/saved-searches/${id}`, { method: "DELETE" });
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <label className="flex items-center gap-1 text-sm text-sand-700">
        {s.alert}
        <select
          value={value}
          disabled={busy}
          onChange={(e) => change(e.target.value as (typeof FREQUENCIES)[number])}
          className="h-9 rounded-lg border border-sand-200 bg-white px-2 text-sm"
        >
          {FREQUENCIES.map((f) => (
            <option key={f} value={f}>
              {s.frequencies[f]}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        onClick={remove}
        disabled={busy}
        className="rounded-lg px-3 py-1.5 text-sm text-danger hover:bg-sand-100"
      >
        {s.delete}
      </button>
    </>
  );
}
