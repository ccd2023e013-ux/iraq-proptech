"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { AuthSessionInfo, User } from "@/types/auth";

type Status = { tone: "success" | "error"; text: string } | null;

export function ProfileForm({ dict, user }: { dict: Dictionary; user: User }) {
  const router = useRouter();
  const [fullName, setFullName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone ?? "");
  const [locale, setLocale] = useState<Locale>(user.preferred_locale);
  const [status, setStatus] = useState<Status>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setStatus(null);
    try {
      await apiFetch("/api/v1/users/me", {
        method: "PATCH",
        body: { full_name: fullName, phone: phone.trim() || null, preferred_locale: locale },
      });
      setStatus({ tone: "success", text: dict.account.saved });
      router.refresh();
    } catch (err) {
      setStatus({ tone: "error", text: describeError(dict, err) });
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
      {status && (
        <div className="sm:col-span-2">
          <Alert tone={status.tone}>{status.text}</Alert>
        </div>
      )}
      <TextField
        label={dict.auth.fullName}
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
        required
      />
      <TextField label={dict.auth.email} value={user.email} dir="ltr" disabled readOnly />
      <TextField
        label={dict.auth.phone}
        type="tel"
        dir="ltr"
        hint={dict.auth.phoneHint}
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
      />
      <div className="flex flex-col gap-1.5">
        <label htmlFor="locale" className="text-sm font-medium text-sand-900">
          {dict.account.language}
        </label>
        <select
          id="locale"
          value={locale}
          onChange={(e) => setLocale(e.target.value as Locale)}
          className="h-11 surface-1 rounded-2xl px-3"
        >
          <option value="ar">العربية</option>
          <option value="en">English</option>
        </select>
      </div>
      <div className="sm:col-span-2">
        <Button type="submit" loading={pending}>
          {dict.account.save}
        </Button>
      </div>
    </form>
  );
}

export function ChangePasswordForm({ dict }: { dict: Dictionary }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [status, setStatus] = useState<Status>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setStatus(null);
    try {
      await apiFetch("/api/v1/auth/password/change", {
        method: "POST",
        body: { current_password: current, new_password: next },
      });
      setCurrent("");
      setNext("");
      setStatus({ tone: "success", text: dict.account.passwordChanged });
    } catch (err) {
      setStatus({ tone: "error", text: describeError(dict, err) });
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex max-w-md flex-col gap-4">
      {status && <Alert tone={status.tone}>{status.text}</Alert>}
      <TextField
        label={dict.auth.currentPassword}
        type="password"
        autoComplete="current-password"
        dir="ltr"
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        required
      />
      <TextField
        label={dict.auth.newPassword}
        type="password"
        autoComplete="new-password"
        dir="ltr"
        hint={dict.auth.passwordHint}
        value={next}
        onChange={(e) => setNext(e.target.value)}
        required
      />
      <div>
        <Button type="submit" variant="secondary" loading={pending}>
          {dict.account.changePassword}
        </Button>
      </div>
    </form>
  );
}

export function SessionsList({ dict, locale }: { dict: Dictionary; locale: Locale }) {
  const router = useRouter();
  const [sessions, setSessions] = useState<AuthSessionInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<AuthSessionInfo[]>("/api/v1/auth/sessions")
      .then(setSessions)
      .catch((err: unknown) => setError(describeError(dict, err)));
  }, [dict]);

  useEffect(load, [load]);

  async function revoke(id: string) {
    try {
      await apiFetch(`/api/v1/auth/sessions/${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(describeError(dict, err));
    }
  }

  async function logoutAll() {
    try {
      await apiFetch("/api/v1/auth/logout-all", { method: "POST" });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  const fmt = new Intl.DateTimeFormat(locale === "ar" ? "ar-IQ" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <div className="flex flex-col gap-3">
      {error && <Alert tone="error">{error}</Alert>}
      {sessions === null && !error && <p className="text-sm text-sand-500">{dict.auth.loading}</p>}
      <ul className="divide-y divide-sand-100">
        {sessions?.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-sand-900" dir="ltr">
                {s.user_agent ?? dict.account.unknownDevice}
              </p>
              <p className="text-xs text-sand-500">
                {dict.account.lastActive}: {fmt.format(new Date(s.last_used_at))}
              </p>
            </div>
            {s.current ? (
              <span className="text-xs font-medium text-success">{dict.account.currentDevice}</span>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => revoke(s.id)}>
                {dict.account.revoke}
              </Button>
            )}
          </li>
        ))}
      </ul>
      <div>
        <Button variant="danger" size="sm" onClick={logoutAll}>
          {dict.account.logoutAll}
        </Button>
      </div>
    </div>
  );
}

export function ResendVerification({ dict }: { dict: Dictionary }) {
  const [state, setState] = useState<"idle" | "sent" | "error">("idle");
  return state === "sent" ? (
    <span className="text-sm">{dict.auth.resent}</span>
  ) : (
    <Button
      size="sm"
      variant="secondary"
      onClick={() =>
        apiFetch("/api/v1/auth/resend-verification", { method: "POST" })
          .then(() => setState("sent"))
          .catch(() => setState("error"))
      }
    >
      {state === "error" ? dict.errors.UNKNOWN : dict.auth.resend}
    </Button>
  );
}
