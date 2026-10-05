"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

const REASONS = [
  "FAKE",
  "DUPLICATE",
  "INCORRECT",
  "INAPPROPRIATE",
  "SCAM",
  "SPAM",
  "OTHER",
] as const;

export function ReportButton({
  dict,
  targetType,
  targetId,
}: {
  dict: Dictionary;
  targetType: "PROPERTY" | "USER" | "AGENCY";
  targetId: string;
}) {
  const a = dict.admin;
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<(typeof REASONS)[number]>("FAKE");
  const [details, setDetails] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setState("busy");
    setError(null);
    try {
      await apiFetch("/api/v1/reports", {
        method: "POST",
        body: {
          target_type: targetType,
          target_id: targetId,
          reason,
          details: details.trim() || null,
        },
      });
      setState("sent");
    } catch (err) {
      setError(describeError(dict, err));
      setState("idle");
    }
  }

  if (state === "sent") return <p className="text-sm text-success">{a.reportSent}</p>;
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-sand-500 underline"
      >
        {a.reportListing}
      </button>
    );
  }
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2 text-sm" aria-label={a.reportListing}>
      <select
        aria-label={a.reportListing}
        value={reason}
        onChange={(e) => setReason(e.target.value as (typeof REASONS)[number])}
        className="h-9 rounded-md border border-sand-200 bg-surface px-2"
      >
        {REASONS.map((r) => (
          <option key={r} value={r}>
            {a.reportReasons[r]}
          </option>
        ))}
      </select>
      <textarea
        value={details}
        onChange={(e) => setDetails(e.target.value)}
        placeholder={a.reportDetails}
        aria-label={a.reportDetails}
        maxLength={2000}
        rows={2}
        className="rounded-md border border-sand-200 p-2"
      />
      {error && <p className="text-xs text-danger">{error}</p>}
      <Button type="submit" size="sm" loading={state === "busy"}>
        {a.report}
      </Button>
    </form>
  );
}
