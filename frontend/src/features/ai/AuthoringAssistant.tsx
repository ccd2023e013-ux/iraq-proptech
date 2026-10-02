"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { AIEnvelope } from "@/types/ai";

/**
 * AI drafting help inside the listing form. Suggestions are never applied
 * automatically: the lister chooses what to use.
 */
export function AuthoringAssistant({
  dict,
  propertyId,
  currentDescription,
  onUseDescription,
  onUseTitle,
}: {
  dict: Dictionary;
  propertyId: string | null;
  currentDescription: string;
  onUseDescription: (text: string) => void;
  onUseTitle: (text: string) => void;
}) {
  const a = dict.ai;
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState<string | null>(null);
  const [titles, setTitles] = useState<string[]>([]);

  async function run(kind: string, fn: () => Promise<void>) {
    setBusy(kind);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-dashed border-brand-300 bg-brand-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-brand-700 px-1.5 py-0.5 text-[11px] font-bold text-white">
          {a.badge}
        </span>
        {propertyId && (
          <>
            <Button
              size="sm"
              variant="secondary"
              loading={busy === "description"}
              onClick={() =>
                run("description", async () => {
                  const r = await apiFetch<AIEnvelope<{ description: string }>>(
                    `/api/v1/ai/listings/${propertyId}/description`,
                    { method: "POST", body: { language: "ar" } },
                  );
                  setDescription(r.result.description);
                })
              }
            >
              {a.generateDescription}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              loading={busy === "titles"}
              onClick={() =>
                run("titles", async () => {
                  const r = await apiFetch<AIEnvelope<{ titles: string[] }>>(
                    `/api/v1/ai/listings/${propertyId}/title`,
                    { method: "POST", body: { language: "ar" } },
                  );
                  setTitles(r.result.titles);
                })
              }
            >
              {a.suggestTitles}
            </Button>
          </>
        )}
        <Button
          size="sm"
          variant="secondary"
          disabled={currentDescription.trim().length < 5}
          loading={busy === "improve"}
          onClick={() =>
            run("improve", async () => {
              const r = await apiFetch<AIEnvelope<{ text: string }>>(
                "/api/v1/ai/text/improve-arabic",
                {
                  method: "POST",
                  body: { text: currentDescription },
                },
              );
              setDescription(r.result.text);
            })
          }
        >
          {a.improveArabic}
        </Button>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
      {description && (
        <div className="flex flex-col gap-2 rounded-md bg-white p-3 text-sm">
          <p className="whitespace-pre-line">{description}</p>
          <p className="text-xs text-sand-500">{a.draftNote}</p>
          <Button size="sm" onClick={() => onUseDescription(description)}>
            {a.useThis}
          </Button>
        </div>
      )}
      {titles.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {titles.map((t) => (
            <li
              key={t}
              className="flex items-center justify-between gap-2 rounded-md bg-white px-3 py-1.5"
            >
              <span>{t}</span>
              <button
                type="button"
                className="text-xs font-medium text-brand-700"
                onClick={() => onUseTitle(t)}
              >
                {a.useThis}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
