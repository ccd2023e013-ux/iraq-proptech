"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

/**
 * A button that performs one admin API call, optionally asking for text first
 * (e.g. a reason), then refreshes the page. `body` may reference `{text}`.
 */
export function ActionButton({
  dict,
  label,
  path,
  method = "POST",
  body,
  prompt,
  tone = "neutral",
}: {
  dict: Dictionary;
  label: string;
  path: string;
  method?: "POST" | "PUT" | "PATCH" | "DELETE";
  body?: Record<string, unknown>;
  prompt?: string;
  tone?: "neutral" | "good" | "bad";
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    let text: string | null = null;
    if (prompt) {
      text = window.prompt(prompt);
      if (text === null || !text.trim()) return;
    }
    const payload = body
      ? Object.fromEntries(
          Object.entries(body).map(([k, v]) => [k, v === "{text}" ? text?.trim() : v]),
        )
      : undefined;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(path, { method, body: payload });
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  const colors = {
    neutral: "border-sand-200 text-sand-800",
    good: "border-success text-success",
    bad: "border-danger text-danger",
  }[tone];
  return (
    <span className="inline-flex flex-col">
      <button
        type="button"
        onClick={run}
        disabled={busy}
        className={`rounded-md border bg-white px-2.5 py-1 text-xs font-medium disabled:opacity-50 ${colors}`}
      >
        {label}
      </button>
      {error && <span className="text-[11px] text-danger">{error}</span>}
    </span>
  );
}
