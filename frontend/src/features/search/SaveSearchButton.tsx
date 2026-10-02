"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

/** Saves the current filters (already validated by the API) as a named search. */
export function SaveSearchButton({
  dict,
  filters,
  signedIn,
  nextPath,
}: {
  dict: Dictionary;
  filters: Record<string, unknown>;
  signedIn: boolean;
  nextPath: string;
}) {
  const router = useRouter();
  const s = dict.savedSearches;
  const [state, setState] = useState<"idle" | "busy" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!signedIn) {
      router.push(`/login?next=${encodeURIComponent(nextPath)}`);
      return;
    }
    const name = window.prompt(s.namePrompt, s.defaultName);
    if (name === null) return;
    setState("busy");
    setError(null);
    try {
      await apiFetch("/api/v1/me/saved-searches", {
        method: "POST",
        body: { name: name.trim() || s.defaultName, filters },
      });
      setState("saved");
    } catch (err) {
      setError(describeError(dict, err));
      setState("idle");
    }
  }

  return (
    <span className="flex items-center gap-2">
      <button
        type="button"
        onClick={save}
        disabled={state !== "idle"}
        className="rounded-lg border border-sand-200 bg-white px-3 py-1.5 text-sm font-medium text-brand-700 hover:border-brand-300 disabled:opacity-60"
      >
        {state === "saved" ? `✓ ${s.saved}` : signedIn ? s.save : s.loginToSave}
      </button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </span>
  );
}
