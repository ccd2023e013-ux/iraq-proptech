"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TextField } from "@/components/ui/TextField";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { Agency, AgencyInvitation, AgencyMember } from "@/types/property";

type Status = { tone: "success" | "error"; text: string } | null;

export function CreateAgencyForm({ dict }: { dict: Dictionary }) {
  const router = useRouter();
  const a = dict.agency;
  const [form, setForm] = useState({
    name_ar: "",
    name_en: "",
    phone: "",
    license_number: "",
    address: "",
  });
  const [status, setStatus] = useState<Status>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setStatus(null);
    try {
      await apiFetch<Agency>("/api/v1/agencies", {
        method: "POST",
        body: Object.fromEntries(
          Object.entries(form).map(([k, v]) => [k, v.trim() === "" ? null : v.trim()]),
        ),
      });
      router.refresh();
    } catch (err) {
      setStatus({ tone: "error", text: describeError(dict, err) });
    } finally {
      setPending(false);
    }
  }

  return (
    <Card title={a.create} description={a.createNote}>
      <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
        {status && (
          <div className="sm:col-span-2">
            <Alert tone={status.tone}>{status.text}</Alert>
          </div>
        )}
        <TextField
          label={a.nameAr}
          required
          value={form.name_ar}
          onChange={(e) => setForm({ ...form, name_ar: e.target.value })}
        />
        <TextField
          label={a.nameEn}
          dir="ltr"
          value={form.name_en}
          onChange={(e) => setForm({ ...form, name_en: e.target.value })}
        />
        <TextField
          label={a.phone}
          dir="ltr"
          type="tel"
          value={form.phone}
          onChange={(e) => setForm({ ...form, phone: e.target.value })}
        />
        <TextField
          label={a.license}
          value={form.license_number}
          onChange={(e) => setForm({ ...form, license_number: e.target.value })}
        />
        <TextField
          className="sm:col-span-2"
          label={a.address}
          value={form.address}
          onChange={(e) => setForm({ ...form, address: e.target.value })}
        />
        <div>
          <Button type="submit" loading={pending}>
            {a.create}
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function AgencyTeam({
  dict,
  agency,
  members,
  isOwner,
}: {
  dict: Dictionary;
  agency: Agency;
  members: AgencyMember[];
  isOwner: boolean;
}) {
  const router = useRouter();
  const a = dict.agency;
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>(null);

  async function invite(event: FormEvent) {
    event.preventDefault();
    setStatus(null);
    try {
      await apiFetch(`/api/v1/agencies/${agency.id}/invitations`, {
        method: "POST",
        body: { email },
      });
      setEmail("");
      setStatus({ tone: "success", text: a.invited });
    } catch (err) {
      setStatus({ tone: "error", text: describeError(dict, err) });
    }
  }

  async function remove(userId: string) {
    try {
      await apiFetch(`/api/v1/agencies/${agency.id}/members/${userId}`, { method: "DELETE" });
      router.refresh();
    } catch (err) {
      setStatus({ tone: "error", text: describeError(dict, err) });
    }
  }

  return (
    <Card title={a.members}>
      {status && (
        <div className="mb-4">
          <Alert tone={status.tone}>{status.text}</Alert>
        </div>
      )}
      <ul className="divide-y divide-sand-100">
        {members.map((m) => (
          <li key={m.user_id} className="flex items-center justify-between gap-3 py-3 text-sm">
            <span className="font-medium">{m.full_name}</span>
            <span className="flex items-center gap-3">
              <span className="text-sand-500">{m.role === "OWNER" ? a.owner : a.agent}</span>
              {isOwner && m.role !== "OWNER" && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-danger"
                  onClick={() => remove(m.user_id)}
                >
                  {a.removeMember}
                </Button>
              )}
            </span>
          </li>
        ))}
      </ul>
      {isOwner && (
        <form onSubmit={invite} className="mt-4 flex flex-wrap items-end gap-3">
          <TextField
            className="min-w-64 flex-1"
            label={a.inviteEmail}
            type="email"
            dir="ltr"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" variant="secondary">
            {a.invite}
          </Button>
        </form>
      )}
    </Card>
  );
}

export function PendingInvitations({
  dict,
  invitations,
}: {
  dict: Dictionary;
  invitations: AgencyInvitation[];
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  if (!invitations.length) return null;

  async function accept(id: string) {
    try {
      await apiFetch(`/api/v1/agency-invitations/${id}/accept`, { method: "POST" });
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    }
  }

  return (
    <Card title={dict.agency.invitations}>
      {error && <Alert tone="error">{error}</Alert>}
      <ul className="divide-y divide-sand-100">
        {invitations.map((inv) => (
          <li key={inv.id} className="flex items-center justify-between gap-3 py-3 text-sm">
            <span className="font-medium">{inv.agency_name}</span>
            <Button size="sm" onClick={() => accept(inv.id)}>
              {dict.agency.accept}
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
