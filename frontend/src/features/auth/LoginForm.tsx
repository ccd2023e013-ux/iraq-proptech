"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { PasswordField } from "@/components/ui/PasswordField";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { safeNextPath } from "@/lib/auth/routing";
import { describeError } from "@/lib/errors";

import { type FieldErrors, validateAuth } from "./validation";

export function LoginForm({ dict, next }: { dict: Dictionary; next?: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fields, setFields] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateAuth(dict, { email, password }, "login");
    setFields(found);
    if (Object.keys(found).length) return;
    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/login", {
        method: "POST",
        body: { email: email.trim(), password },
      });
      router.replace(safeNextPath(next));
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <TextField
        label={dict.auth.email}
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        dir="ltr"
        required
        error={fields.email}
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <div className="flex flex-col gap-2">
        <PasswordField
          label={dict.auth.password}
          name="password"
          autoComplete="current-password"
          dir="ltr"
          required
          showLabel={dict.auth.show}
          hideLabel={dict.auth.hide}
          error={fields.password}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Link
          href="/forgot-password"
          className="self-end text-sm text-accent underline-offset-4 hover:underline"
        >
          {dict.auth.forgotLink}
        </Link>
      </div>
      <Button type="submit" size="lg" block loading={pending}>
        {dict.auth.submitLogin}
      </Button>
    </form>
  );
}
