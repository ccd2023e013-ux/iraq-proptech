"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

export function WebhookForm({ dict, events }: { dict: Dictionary; events: string[] }) {
  const router = useRouter();
  const a = dict.admin;
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [secret, setSecret] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await apiFetch<{ secret: string }>("/api/v1/admin/webhooks", {
        method: "POST",
        body: { name: name.trim(), url: url.trim(), events: selected.length ? selected : ["*"] },
      });
      setSecret(created.secret);
      setName("");
      setUrl("");
      setSelected([]);
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 surface-1 rounded-2xl p-4 text-sm">
      <h2 className="font-semibold">{a.newWebhook}</h2>
      <p className="text-xs text-sand-500">{a.n8nHint}</p>
      <input
        required
        minLength={2}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="n8n"
        aria-label="name"
        className="h-10 rounded-md border border-sand-200 px-3"
      />
      <input
        required
        type="url"
        dir="ltr"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://n8n.example.com/webhook/…"
        aria-label={a.url}
        className="h-10 rounded-md border border-sand-200 px-3"
      />
      <fieldset className="flex flex-wrap gap-2">
        <legend className="mb-1 text-xs text-sand-700">{a.events}</legend>
        {events.map((ev) => {
          const on = selected.includes(ev);
          return (
            <button
              key={ev}
              type="button"
              aria-pressed={on}
              onClick={() => setSelected(on ? selected.filter((x) => x !== ev) : [...selected, ev])}
              className={`rounded-[var(--radius-tag)] border px-2.5 py-0.5 font-mono text-[11px] ${on ? "border-brand-600 bg-brand-600 text-on-accent" : "border-sand-200"}`}
              dir="ltr"
            >
              {ev}
            </button>
          );
        })}
      </fieldset>
      {error && <p className="text-danger">{error}</p>}
      {secret && (
        <p className="rounded-md bg-gold-100 p-2 text-xs">
          {a.secretOnce}{" "}
          <code dir="ltr" className="break-all">
            {secret}
          </code>
        </p>
      )}
      <Button type="submit" loading={busy}>
        {a.create}
      </Button>
    </form>
  );
}
