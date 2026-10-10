"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import {
  type Appointment,
  type Lead,
  type LeadStatus,
  MANUAL_ACTIVITY_KINDS,
  type Priority,
  type Task,
} from "@/types/crm";

import { formatDateTime, fromLocalInput, toLocalInput } from "./labels";

const field = "h-10 w-full surface-1 rounded-2xl px-3 text-sm";
const labelCls = "flex flex-col gap-1 text-xs font-medium text-sand-700";

function useAction(dict: Dictionary) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(fn: () => Promise<unknown>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      await fn();
      router.refresh();
      return true;
    } catch (err) {
      setError(describeError(dict, err));
      return false;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, run };
}

export function LeadEditor({
  dict,
  locale,
  lead,
  statuses,
  members,
}: {
  dict: Dictionary;
  locale: Locale;
  lead: Lead;
  statuses: LeadStatus[];
  members: { user_id: string; full_name: string }[];
}) {
  const c = dict.crm;
  const { busy, error, run } = useAction(dict);
  const [status, setStatus] = useState(lead.status_code);
  const [lostReason, setLostReason] = useState(lead.lost_reason ?? "");
  const [priority, setPriority] = useState<Priority>(lead.priority);
  const [followUp, setFollowUp] = useState(toLocalInput(lead.next_follow_up_at));
  const [assignee, setAssignee] = useState(lead.assigned_to?.id ?? "");
  const [budgetMin, setBudgetMin] = useState(lead.budget_min ?? "");
  const [budgetMax, setBudgetMax] = useState(lead.budget_max ?? "");
  const [currency, setCurrency] = useState(lead.budget_currency ?? "IQD");
  const [saved, setSaved] = useState(false);
  const disabled = !lead.can_manage || busy;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    const body: Record<string, unknown> = {
      priority,
      next_follow_up_at: fromLocalInput(followUp),
    };
    if (status !== lead.status_code) {
      body.status_code = status;
      if (status === "LOST") body.lost_reason = lostReason;
    }
    if (lead.can_assign && assignee && assignee !== lead.assigned_to?.id)
      body.assigned_to_id = assignee;
    const hasBudget = budgetMin !== "" || budgetMax !== "";
    if (hasBudget || lead.budget_currency) {
      body.budget_min = budgetMin === "" ? null : budgetMin;
      body.budget_max = budgetMax === "" ? null : budgetMax;
      body.budget_currency = hasBudget ? currency : null;
    }
    const ok = await run(() => apiFetch(`/api/v1/crm/leads/${lead.id}`, { method: "PATCH", body }));
    setSaved(ok);
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2">
      {error && (
        <div className="sm:col-span-2">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <label className={labelCls}>
        {c.status}
        <select
          className={field}
          value={status}
          disabled={disabled}
          onChange={(e) => setStatus(e.target.value)}
        >
          {statuses
            .filter((s) => s.is_active || s.code === lead.status_code)
            .map((s) => (
              <option key={s.code} value={s.code}>
                {locale === "ar" ? s.name_ar : s.name_en}
              </option>
            ))}
        </select>
      </label>
      <label className={labelCls}>
        {c.priority}
        <select
          className={field}
          value={priority}
          disabled={disabled}
          onChange={(e) => setPriority(e.target.value as Priority)}
        >
          {(["LOW", "NORMAL", "HIGH"] as const).map((p) => (
            <option key={p} value={p}>
              {c.priorities[p]}
            </option>
          ))}
        </select>
      </label>
      {status === "LOST" && (
        <label className={`${labelCls} sm:col-span-2`}>
          {c.lostReason}
          <input
            className={field}
            value={lostReason}
            required
            disabled={disabled}
            onChange={(e) => setLostReason(e.target.value)}
          />
        </label>
      )}
      <label className={labelCls}>
        {c.followUp}
        <input
          type="datetime-local"
          className={field}
          value={followUp}
          disabled={disabled}
          onChange={(e) => setFollowUp(e.target.value)}
        />
      </label>
      {lead.can_assign && members.length > 0 && (
        <label className={labelCls}>
          {c.assignedTo}
          <select
            className={field}
            value={assignee}
            disabled={disabled}
            onChange={(e) => setAssignee(e.target.value)}
          >
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.full_name}
              </option>
            ))}
          </select>
        </label>
      )}
      <fieldset className="grid grid-cols-[1fr_1fr_auto] gap-2 sm:col-span-2">
        <legend className="mb-1 text-xs font-medium text-sand-700">{c.budget}</legend>
        <input
          className={field}
          dir="ltr"
          inputMode="numeric"
          aria-label={`${c.budget} min`}
          value={budgetMin}
          disabled={disabled}
          onChange={(e) => setBudgetMin(e.target.value.replace(/[^\d.]/g, ""))}
        />
        <input
          className={field}
          dir="ltr"
          inputMode="numeric"
          aria-label={`${c.budget} max`}
          value={budgetMax}
          disabled={disabled}
          onChange={(e) => setBudgetMax(e.target.value.replace(/[^\d.]/g, ""))}
        />
        <select
          className={`${field} w-auto`}
          aria-label={dict.listingForm.currency}
          value={currency}
          disabled={disabled}
          onChange={(e) => setCurrency(e.target.value as "IQD" | "USD")}
        >
          <option value="IQD">IQD</option>
          <option value="USD">USD</option>
        </select>
      </fieldset>
      {lead.can_manage && (
        <div className="flex items-center gap-3 sm:col-span-2">
          <Button type="submit" loading={busy}>
            {c.save}
          </Button>
          {saved && <span className="text-sm text-success">{c.saved}</span>}
        </div>
      )}
    </form>
  );
}

export function ActivityForm({ dict, leadId }: { dict: Dictionary; leadId: string }) {
  const c = dict.crm;
  const { busy, error, run } = useAction(dict);
  const [kind, setKind] = useState<(typeof MANUAL_ACTIVITY_KINDS)[number]>("NOTE");
  const [body, setBody] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const ok = await run(() =>
      apiFetch(`/api/v1/crm/leads/${leadId}/activities`, {
        method: "POST",
        body: { kind, body: body.trim() },
      }),
    );
    if (ok) setBody("");
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2" aria-label={c.logActivity}>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="flex gap-2">
        <select
          aria-label={c.logActivity}
          className={`${field} w-36`}
          value={kind}
          onChange={(e) => setKind(e.target.value as (typeof MANUAL_ACTIVITY_KINDS)[number])}
        >
          {MANUAL_ACTIVITY_KINDS.map((k) => (
            <option key={k} value={k}>
              {c.activityKinds[k]}
            </option>
          ))}
        </select>
        <input
          className={field}
          aria-label={c.activityBody}
          placeholder={c.activityBody}
          value={body}
          required
          onChange={(e) => setBody(e.target.value)}
        />
        <Button type="submit" loading={busy}>
          {c.add}
        </Button>
      </div>
    </form>
  );
}

export function TaskPanel({
  dict,
  locale,
  leadId,
  tasks,
  canManage,
}: {
  dict: Dictionary;
  locale: Locale;
  leadId: string | null;
  tasks: Task[];
  canManage: boolean;
}) {
  const c = dict.crm;
  const { busy, error, run } = useAction(dict);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");

  async function add(event: FormEvent) {
    event.preventDefault();
    const ok = await run(() =>
      apiFetch("/api/v1/crm/tasks", {
        method: "POST",
        body: { title: title.trim(), lead_id: leadId, due_at: fromLocalInput(due) },
      }),
    );
    if (ok) {
      setTitle("");
      setDue("");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <Alert tone="error">{error}</Alert>}
      {tasks.length === 0 ? (
        <p className="text-sm text-sand-500">{c.noTasks}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {tasks.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-3 text-sm">
              <span className={t.completed_at ? "text-sand-500 line-through" : ""}>
                {t.title}
                {t.due_at && (
                  <span className={`ms-2 text-xs ${t.overdue ? "text-danger" : "text-sand-500"}`}>
                    {t.overdue ? `${c.overdue} · ` : ""}
                    {formatDateTime(t.due_at, locale)}
                  </span>
                )}
                {t.assigned_to && (
                  <span className="ms-2 text-xs text-sand-500">{t.assigned_to.full_name}</span>
                )}
              </span>
              {canManage && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    run(() =>
                      apiFetch(`/api/v1/crm/tasks/${t.id}`, {
                        method: "PATCH",
                        body: { completed: !t.completed_at },
                      }),
                    )
                  }
                  className="rounded-md border border-sand-200 px-2 py-1 text-xs"
                >
                  {t.completed_at ? c.reopen : c.complete}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canManage && (
        <form onSubmit={add} className="flex flex-wrap gap-2" aria-label={c.newTask}>
          <input
            className={`${field} min-w-40 flex-1`}
            placeholder={c.taskTitle}
            aria-label={c.taskTitle}
            value={title}
            required
            minLength={2}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input
            type="datetime-local"
            className={`${field} w-auto`}
            aria-label={c.due}
            value={due}
            onChange={(e) => setDue(e.target.value)}
          />
          <Button type="submit" loading={busy}>
            {c.add}
          </Button>
        </form>
      )}
    </div>
  );
}

export function AppointmentPanel({
  dict,
  locale,
  leadId,
  appointments,
  canManage,
}: {
  dict: Dictionary;
  locale: Locale;
  leadId: string;
  appointments: Appointment[];
  canManage: boolean;
}) {
  const c = dict.crm;
  const { busy, error, run } = useAction(dict);
  const [startsAt, setStartsAt] = useState("");
  const [location, setLocation] = useState("");

  async function add(event: FormEvent) {
    event.preventDefault();
    const iso = fromLocalInput(startsAt);
    if (!iso) return;
    const ok = await run(() =>
      apiFetch(`/api/v1/crm/leads/${leadId}/appointments`, {
        method: "POST",
        body: { starts_at: iso, location_text: location.trim() || null },
      }),
    );
    if (ok) {
      setStartsAt("");
      setLocation("");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <Alert tone="error">{error}</Alert>}
      <ul className="flex flex-col gap-2 text-sm">
        {appointments.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {formatDateTime(a.starts_at, locale)}
              {a.location_text && <span className="ms-2 text-sand-500">{a.location_text}</span>}
            </span>
            {canManage ? (
              <select
                aria-label={c.status}
                className="h-8 rounded-md border border-sand-200 bg-surface px-2 text-xs"
                value={a.status}
                disabled={busy}
                onChange={(e) =>
                  run(() =>
                    apiFetch(`/api/v1/crm/appointments/${a.id}`, {
                      method: "PATCH",
                      body: { status: e.target.value },
                    }),
                  )
                }
              >
                {(["SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"] as const).map((s) => (
                  <option key={s} value={s}>
                    {c.appointmentStatuses[s]}
                  </option>
                ))}
              </select>
            ) : (
              <span>{c.appointmentStatuses[a.status]}</span>
            )}
          </li>
        ))}
      </ul>
      {canManage && (
        <form onSubmit={add} className="flex flex-wrap gap-2" aria-label={c.newAppointment}>
          <input
            type="datetime-local"
            className={`${field} w-auto`}
            aria-label={c.startsAt}
            value={startsAt}
            required
            onChange={(e) => setStartsAt(e.target.value)}
          />
          <input
            className={`${field} min-w-32 flex-1`}
            placeholder={c.location}
            aria-label={c.location}
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
          <Button type="submit" loading={busy}>
            {c.add}
          </Button>
        </form>
      )}
    </div>
  );
}

export function ReplyDraft({ dict, leadId }: { dict: Dictionary; leadId: string }) {
  const [text, setText] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function draft() {
    setBusy(true);
    setError(null);
    try {
      const r = await apiFetch<{ result: { reply: string } }>(
        `/api/v1/ai/leads/${leadId}/reply-draft`,
        {
          method: "POST",
          body: { language: "ar" },
        },
      );
      setText(r.result.reply);
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Button size="sm" variant="secondary" loading={busy} onClick={draft}>
        {dict.ai.replyDraft}
      </Button>
      {error && <p className="text-sm text-danger">{error}</p>}
      {text && (
        <textarea
          readOnly
          value={text}
          rows={6}
          aria-label={dict.ai.replyDraft}
          className="surface-1 rounded-2xl p-2 text-sm"
        />
      )}
    </div>
  );
}
