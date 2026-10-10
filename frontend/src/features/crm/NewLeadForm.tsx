"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { Lead, LeadSource } from "@/types/crm";

const SOURCES: LeadSource[] = [
  "PHONE",
  "WHATSAPP",
  "WALK_IN",
  "REFERRAL",
  "SOCIAL",
  "MANUAL",
  "OTHER",
];

export function NewLeadForm({ dict }: { dict: Dictionary }) {
  const router = useRouter();
  const c = dict.crm;
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [source, setSource] = useState<LeadSource>("PHONE");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const lead = await apiFetch<Lead>("/api/v1/crm/leads", {
        method: "POST",
        body: {
          customer: { full_name: name.trim(), phone: phone.trim() || null },
          source,
          note: note.trim() || null,
        },
      });
      router.push(`/dashboard/crm/leads/${lead.id}`);
    } catch (err) {
      setError(describeError(dict, err));
      setBusy(false);
    }
  }

  if (!open) {
    return <Button onClick={() => setOpen(true)}>{c.newLead}</Button>;
  }
  return (
    <form
      onSubmit={onSubmit}
      className="grid gap-3 surface-1 rounded-[var(--radius-card)] p-4 sm:grid-cols-2"
    >
      {error && (
        <div className="sm:col-span-2">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <TextField
        label={c.customerName}
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        minLength={2}
      />
      <TextField
        label={dict.inquiry.phone}
        dir="ltr"
        inputMode="tel"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
      />
      <label className="flex flex-col gap-1.5 text-sm font-medium text-sand-900">
        {c.source}
        <select
          value={source}
          onChange={(e) => setSource(e.target.value as LeadSource)}
          className="h-11 surface-1 rounded-2xl px-3"
        >
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {c.sources[s]}
            </option>
          ))}
        </select>
      </label>
      <TextField label={c.notes} value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="flex gap-2 sm:col-span-2">
        <Button type="submit" loading={busy}>
          {c.create}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          {dict.map.cancelDrawing}
        </Button>
      </div>
    </form>
  );
}
