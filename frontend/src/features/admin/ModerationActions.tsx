"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

const CODES = [
  "INCOMPLETE",
  "MISLEADING",
  "DUPLICATE",
  "WRONG_CATEGORY",
  "POOR_PHOTOS",
  "PROHIBITED_CONTENT",
  "SUSPECTED_FRAUD",
  "CONTACT_IN_TEXT",
  "REPORTED",
  "OTHER",
] as const;

/** Approve / reject / suspend with a reason code and a message for the lister. */
export function ModerationActions({
  dict,
  propertyId,
  status,
}: {
  dict: Dictionary;
  propertyId: string;
  status: string;
}) {
  const router = useRouter();
  const a = dict.admin;
  const [code, setCode] = useState<(typeof CODES)[number]>("INCOMPLETE");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: "APPROVE" | "REJECT" | "SUSPEND" | "REINSTATE") {
    let reason: string | null = null;
    if (decision === "REJECT" || decision === "SUSPEND") {
      reason = window.prompt(a.reasonPrompt);
      if (!reason?.trim()) return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/properties/${propertyId}/moderate`, {
        method: "POST",
        body: { decision, reason, ...(reason ? { reason_code: code } : {}) },
      });
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  const btn = "rounded-md border bg-surface px-2.5 py-1 text-xs font-medium disabled:opacity-50";
  return (
    <div className="flex flex-wrap items-center gap-2">
      {status === "PENDING_REVIEW" && (
        <button
          type="button"
          disabled={busy}
          className={`${btn} border-success text-success`}
          onClick={() => decide("APPROVE")}
        >
          {a.approve}
        </button>
      )}
      <select
        aria-label={a.reasonCode}
        value={code}
        onChange={(e) => setCode(e.target.value as (typeof CODES)[number])}
        className="h-7 rounded-md border border-sand-200 bg-surface px-1 text-xs"
      >
        {CODES.map((c) => (
          <option key={c} value={c}>
            {a.reasonCodes[c]}
          </option>
        ))}
      </select>
      {status === "PENDING_REVIEW" && (
        <button
          type="button"
          disabled={busy}
          className={`${btn} border-danger text-danger`}
          onClick={() => decide("REJECT")}
        >
          {a.reject}
        </button>
      )}
      {(status === "APPROVED" || status === "PENDING_REVIEW") && (
        <button
          type="button"
          disabled={busy}
          className={`${btn} border-danger text-danger`}
          onClick={() => decide("SUSPEND")}
        >
          {a.suspend}
        </button>
      )}
      {status === "SUSPENDED" && (
        <button
          type="button"
          disabled={busy}
          className={`${btn} border-success text-success`}
          onClick={() => decide("REINSTATE")}
        >
          {a.reinstate}
        </button>
      )}
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
