"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { safeNextPath } from "@/lib/auth/routing";
import { describeError } from "@/lib/errors";

export function LoginForm({ dict, next }: { dict: Dictionary; next?: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/login", { method: "POST", body: { email, password } });
      router.replace(safeNextPath(next));
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <TextField
        label={dict.auth.email}
        type="email"
        name="email"
        autoComplete="email"
        dir="ltr"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <TextField
        label={dict.auth.password}
        type="password"
        name="password"
        autoComplete="current-password"
        dir="ltr"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" size="lg" block loading={pending}>
        {dict.auth.submitLogin}
      </Button>
    </form>
  );
}
