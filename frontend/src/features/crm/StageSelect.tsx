"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { LeadStatus } from "@/types/crm";

/** Move a lead to another pipeline stage (asks for a reason when it is lost). */
export function StageSelect({
  dict,
  locale,
  leadId,
  current,
  statuses,
  disabled,
}: {
  dict: Dictionary;
  locale: Locale;
  leadId: string;
  current: string;
  statuses: LeadStatus[];
  disabled?: boolean;
}) {
  const router = useRouter();
  const [value, setValue] = useState(current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function change(next: string) {
    let lostReason: string | null = null;
    if (next === "LOST") {
      lostReason = window.prompt(dict.crm.lostReason);
      if (!lostReason?.trim()) {
        setError(dict.crm.lostReasonRequired);
        return;
      }
    }
    setBusy(true);
    setError(null);
    setValue(next);
    try {
      await apiFetch(`/api/v1/crm/leads/${leadId}`, {
        method: "PATCH",
        body: { status_code: next, ...(lostReason ? { lost_reason: lostReason } : {}) },
      });
      router.refresh();
    } catch (err) {
      setValue(current);
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="flex flex-col gap-1">
      <select
        aria-label={dict.crm.moveTo}
        value={value}
        disabled={busy || disabled}
        onChange={(e) => change(e.target.value)}
        onClick={(e) => e.stopPropagation()}
        className="h-8 rounded-md border border-sand-200 bg-surface px-2 text-xs"
      >
        {statuses
          .filter((s) => s.is_active || s.code === current)
          .map((s) => (
            <option key={s.code} value={s.code}>
              {locale === "ar" ? s.name_ar : s.name_en}
            </option>
          ))}
      </select>
      {error && <span className="text-xs text-danger">{error}</span>}
    </span>
  );
}
