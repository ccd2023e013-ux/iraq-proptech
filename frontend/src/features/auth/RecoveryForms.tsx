"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

export function ForgotPasswordForm({ dict }: { dict: Dictionary }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/password/forgot", { method: "POST", body: { email } });
      setSent(true);
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setPending(false);
    }
  }

  if (sent) return <Alert tone="success">{dict.auth.forgotSent}</Alert>;
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <TextField
        label={dict.auth.email}
        type="email"
        autoComplete="email"
        dir="ltr"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Button type="submit" size="lg" block loading={pending}>
        {dict.auth.forgotSubmit}
      </Button>
    </form>
  );
}

export function ResetPasswordForm({ dict, token }: { dict: Dictionary; token: string | null }) {
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!token) return <Alert tone="error">{dict.auth.resetMissingToken}</Alert>;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/password/reset", {
        method: "POST",
        body: { token, new_password: password },
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
        <Alert tone="success">{dict.auth.resetDone}</Alert>
        <Link href="/login" className="text-center font-medium text-brand-700 underline">
          {dict.auth.submitLogin}
        </Link>
      </div>
    );
  }
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <TextField
        label={dict.auth.newPassword}
        type="password"
        autoComplete="new-password"
        dir="ltr"
        required
        hint={dict.auth.passwordHint}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" size="lg" block loading={pending}>
        {dict.auth.resetSubmit}
      </Button>
    </form>
  );
}

export function VerifyEmail({ dict, token }: { dict: Dictionary; token: string | null }) {
  const [state, setState] = useState<"pending" | "ok" | "error">(token ? "pending" : "error");
  const [error, setError] = useState<string | null>(
    token ? null : dict.errors.VERIFICATION_TOKEN_INVALID,
  );
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return; // StrictMode runs effects twice in dev
    started.current = true;
    apiFetch("/api/v1/auth/verify-email", { method: "POST", body: { token } })
      .then(() => setState("ok"))
      .catch((err: unknown) => {
        setError(describeError(dict, err));
        setState("error");
      });
  }, [token, dict]);

  if (state === "pending") return <p className="text-sand-700">{dict.auth.verifying}</p>;
  if (state === "ok") {
    return (
      <div className="flex flex-col gap-4">
        <Alert tone="success">{dict.auth.verified}</Alert>
        <Link href="/dashboard" className="text-center font-medium text-brand-700 underline">
          {dict.nav.dashboard}
        </Link>
      </div>
    );
  }
  return <Alert tone="error">{error}</Alert>;
}
