"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

export interface Prefs {
  email_enabled: boolean;
  sms_enabled: boolean;
  push_enabled: boolean;
  categories: Record<string, boolean>;
}

const CATEGORIES = [
  "leads",
  "messages",
  "listings",
  "saved_searches",
  "reports",
  "reminders",
  "account",
] as const;

export function NotificationPreferences({ dict, initial }: { dict: Dictionary; initial: Prefs }) {
  const n = dict.notifications;
  const [prefs, setPrefs] = useState<Prefs>(initial);
  const [state, setState] = useState<"idle" | "busy" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setState("busy");
    setError(null);
    try {
      await apiFetch("/api/v1/me/notification-preferences", { method: "PUT", body: prefs });
      setState("saved");
    } catch (err) {
      setError(describeError(dict, err));
      setState("idle");
    }
  }

  const toggle = (key: "email_enabled" | "sms_enabled" | "push_enabled") =>
    setPrefs((p) => ({ ...p, [key]: !p[key] }));

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 text-sm" aria-label={n.preferences}>
      <p className="text-xs text-sand-500">{n.inAppNote}</p>
      <fieldset className="flex flex-wrap gap-4">
        {(
          [
            ["email_enabled", n.email],
            ["sms_enabled", n.sms],
            ["push_enabled", n.push],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2">
            <input type="checkbox" checked={prefs[key]} onChange={() => toggle(key)} />
            {label}
          </label>
        ))}
      </fieldset>
      <fieldset className="grid gap-2 sm:grid-cols-2">
        {CATEGORIES.map((c) => (
          <label key={c} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={prefs.categories[c] ?? true}
              onChange={(e) =>
                setPrefs((p) => ({ ...p, categories: { ...p.categories, [c]: e.target.checked } }))
              }
            />
            {n.categories[c]}
          </label>
        ))}
      </fieldset>
      {error && <p className="text-danger">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" loading={state === "busy"}>
          {n.save}
        </Button>
        {state === "saved" && <span className="text-success">{n.saved}</span>}
      </div>
    </form>
  );
}
