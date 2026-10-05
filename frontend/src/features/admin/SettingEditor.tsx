"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

export function SettingEditor({
  dict,
  settingKey,
  value,
}: {
  dict: Dictionary;
  settingKey: string;
  value: unknown;
}) {
  const router = useRouter();
  const kind = typeof value === "boolean" ? "bool" : typeof value === "number" ? "number" : "text";
  const [draft, setDraft] = useState(kind === "bool" ? String(value) : String(value ?? ""));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save() {
    setError(null);
    setSaved(false);
    const parsed = kind === "bool" ? draft === "true" : kind === "number" ? Number(draft) : draft;
    try {
      await apiFetch(`/api/v1/admin/settings/${encodeURIComponent(settingKey)}`, {
        method: "PUT",
        body: { value: parsed },
      });
      setSaved(true);
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {kind === "bool" ? (
        <select
          aria-label={settingKey}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="h-9 rounded-md border border-sand-200 bg-surface px-2 text-sm"
        >
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      ) : (
        <input
          aria-label={settingKey}
          value={draft}
          inputMode={kind === "number" ? "numeric" : undefined}
          onChange={(e) => setDraft(e.target.value)}
          className="h-9 min-w-48 rounded-md border border-sand-200 px-2 text-sm"
        />
      )}
      <button
        type="button"
        onClick={save}
        className="rounded-md bg-brand-700 px-3 py-1.5 text-xs font-medium text-on-accent"
      >
        {dict.admin.save}
      </button>
      {saved && <span className="text-xs text-success">✓</span>}
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
