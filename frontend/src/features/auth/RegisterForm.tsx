"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

type AccountType = "CUSTOMER" | "PROPERTY_OWNER";

export function RegisterForm({ dict, locale }: { dict: Dictionary; locale: Locale }) {
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    account_type: "CUSTOMER" as AccountType,
  });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/register", {
        method: "POST",
        body: { ...form, phone: form.phone.trim() || null, locale },
      });
      setDone(true);
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setPending(false);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col gap-4">
        <Alert tone="success" title={dict.auth.registeredTitle}>
          {dict.auth.registeredBody}
        </Alert>
        <Link
          href="/login"
          className="text-center font-medium text-brand-700 underline underline-offset-4"
        >
          {dict.auth.submitLogin}
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium text-sand-900">{dict.auth.accountType}</legend>
        {(["CUSTOMER", "PROPERTY_OWNER"] as const).map((type) => (
          <label
            key={type}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition ${form.account_type === type ? "border-brand-500 bg-brand-50" : "border-sand-200"}`}
          >
            <input
              type="radio"
              name="account_type"
              value={type}
              checked={form.account_type === type}
              onChange={() => set("account_type")(type)}
              className="accent-brand-700"
            />
            {type === "CUSTOMER" ? dict.auth.accountCustomer : dict.auth.accountOwner}
          </label>
        ))}
      </fieldset>
      <TextField
        label={dict.auth.fullName}
        name="full_name"
        autoComplete="name"
        required
        value={form.full_name}
        onChange={(e) => set("full_name")(e.target.value)}
      />
      <TextField
        label={dict.auth.email}
        type="email"
        name="email"
        autoComplete="email"
        dir="ltr"
        required
        value={form.email}
        onChange={(e) => set("email")(e.target.value)}
      />
      <TextField
        label={dict.auth.phone}
        type="tel"
        name="phone"
        autoComplete="tel"
        dir="ltr"
        hint={dict.auth.phoneHint}
        value={form.phone}
        onChange={(e) => set("phone")(e.target.value)}
      />
      <TextField
        label={dict.auth.password}
        type="password"
        name="password"
        autoComplete="new-password"
        dir="ltr"
        required
        minLength={10}
        hint={dict.auth.passwordHint}
        value={form.password}
        onChange={(e) => set("password")(e.target.value)}
      />
      <Button type="submit" size="lg" block loading={pending}>
        {dict.auth.submitRegister}
      </Button>
    </form>
  );
}
