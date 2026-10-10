"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

const PREFERENCES = ["ANY", "PHONE", "WHATSAPP", "EMAIL"] as const;

export function InquiryForm({
  dict,
  propertyId,
  signedIn,
  defaultName,
  defaultPhone,
  defaultEmail,
}: {
  dict: Dictionary;
  propertyId: string;
  signedIn: boolean;
  defaultName: string;
  defaultPhone: string;
  defaultEmail: string;
}) {
  const t = dict.inquiry;
  const [name, setName] = useState(defaultName);
  const [phone, setPhone] = useState(defaultPhone);
  const [email, setEmail] = useState(defaultEmail);
  const [message, setMessage] = useState(t.defaultMessage);
  const [preferred, setPreferred] = useState<(typeof PREFERENCES)[number]>("ANY");
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  if (!signedIn) {
    return (
      <Link
        href={`/login?next=${encodeURIComponent(`/properties/${propertyId}`)}`}
        className="block rounded-lg border border-brand-300 px-4 py-2.5 text-center text-sm font-medium text-accent"
      >
        {t.loginToSend}
      </Link>
    );
  }

  if (state === "sent") {
    return (
      <div className="flex flex-col gap-2">
        <Alert tone="success">{t.sent}</Alert>
        <Link href="/messages" className="text-sm font-medium text-accent">
          {t.openMessages}
        </Link>
      </div>
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!phone.trim() && !email.trim()) {
      setError(t.contactHint);
      return;
    }
    setState("busy");
    setError(null);
    try {
      await apiFetch(`/api/v1/properties/${propertyId}/inquiries`, {
        method: "POST",
        body: {
          name: name.trim(),
          phone: phone.trim() || null,
          email: email.trim() || null,
          message: message.trim(),
          preferred_contact: preferred,
        },
      });
      setState("sent");
    } catch (err) {
      setError(describeError(dict, err));
      setState("idle");
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3" aria-label={t.title}>
      {error && <Alert tone="error">{error}</Alert>}
      <TextField
        label={t.name}
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        minLength={2}
      />
      <TextField
        label={t.phone}
        dir="ltr"
        inputMode="tel"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
      />
      <TextField
        label={t.email}
        dir="ltr"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <label className="flex flex-col gap-1 text-sm font-medium text-sand-700">
        {t.message}
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          required
          minLength={5}
          maxLength={3000}
          rows={4}
          className="field py-2 text-sm text-sand-900"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium text-sand-700">
        {t.preferred}
        <select
          value={preferred}
          onChange={(e) => setPreferred(e.target.value as (typeof PREFERENCES)[number])}
          className="h-10 surface-1 rounded-2xl px-3 text-sm"
        >
          {PREFERENCES.map((p) => (
            <option key={p} value={p}>
              {t.preferences[p]}
            </option>
          ))}
        </select>
      </label>
      <Button type="submit" loading={state === "busy"} block>
        {t.send}
      </Button>
    </form>
  );
}
