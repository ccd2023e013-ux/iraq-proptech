"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { PasswordField } from "@/components/ui/PasswordField";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

import { type FieldErrors, PASSWORD_MIN, validateAuth } from "./validation";

type AccountType = "CUSTOMER" | "PROPERTY_OWNER";

export function RegisterForm({
  dict,
  locale,
  emailDelivery = true,
}: {
  dict: Dictionary;
  locale: Locale;
  /** Whether the site can send the confirmation email (from /auth/capabilities). */
  emailDelivery?: boolean;
}) {
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    account_type: "CUSTOMER" as AccountType,
  });
  const [fields, setFields] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateAuth(dict, form, "register");
    setFields(found);
    if (Object.keys(found).length) return;
    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/register", {
        method: "POST",
        body: {
          ...form,
          full_name: form.full_name.trim(),
          email: form.email.trim(),
          phone: form.phone.trim() || null,
          locale,
        },
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
          {emailDelivery ? dict.auth.registeredBody : dict.auth.registeredNoEmail}
        </Alert>
        {!emailDelivery && (
          <Alert tone="info" title={dict.auth.emailUnavailableTitle}>
            {dict.auth.emailUnavailable}
          </Alert>
        )}
        <Link
          href="/login"
          className="inline-flex h-12 items-center justify-center rounded-full bg-accent-fill px-6 font-medium text-white transition hover:bg-accent-fill-hover"
        >
          {dict.auth.submitLogin}
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium text-ink">{dict.auth.accountType}</legend>
        {(["CUSTOMER", "PROPERTY_OWNER"] as const).map((type) => (
          <label
            key={type}
            className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-[var(--radius-control)] px-4 py-2.5 text-sm ring-1 ring-inset transition ${form.account_type === type ? "bg-accent-tint text-ink ring-accent" : "bg-fill text-ink-2 ring-transparent hover:text-ink"}`}
          >
            <input
              type="radio"
              name="account_type"
              value={type}
              checked={form.account_type === type}
              onChange={() => set("account_type")(type)}
              className="size-4 accent-[var(--accent)]"
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
        error={fields.full_name}
        value={form.full_name}
        onChange={(e) => set("full_name")(e.target.value)}
      />
      <TextField
        label={dict.auth.email}
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        dir="ltr"
        required
        error={fields.email}
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
      <PasswordField
        label={dict.auth.password}
        name="password"
        autoComplete="new-password"
        dir="ltr"
        required
        minLength={PASSWORD_MIN}
        showLabel={dict.auth.show}
        hideLabel={dict.auth.hide}
        error={fields.password}
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
