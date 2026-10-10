import Link from "next/link";
import { notFound } from "next/navigation";

import { Card } from "@/components/ui/Card";
import {
  ActivityForm,
  AppointmentPanel,
  LeadEditor,
  ReplyDraft,
  TaskPanel,
} from "@/features/crm/LeadPanels";
import { formatDateTime, statusName } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { requireAnyPermission } from "@/lib/auth/guard";
import { formatPrice } from "@/lib/format";
import type { Activity, Appointment, Lead, LeadStatus, Page, Task } from "@/types/crm";

export const dynamic = "force-dynamic";

async function load(id: string): Promise<Lead> {
  try {
    return await serverApiFetch<Lead>(`/api/v1/crm/leads/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof ApiError && [404, 422].includes(error.status)) notFound();
    throw error;
  }
}

export default async function LeadPage({ params }: { params: Promise<{ id: string }> }) {
  await requireAnyPermission(["leads.read_own", "leads.read_agency", "leads.read_any"]);
  const { id } = await params;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const c = dict.crm;
  const lead = await load(id);
  const [statuses, activities, tasks, appointments, members] = await Promise.all([
    serverApiFetch<LeadStatus[]>("/api/v1/crm/statuses"),
    serverApiFetch<Activity[]>(`/api/v1/crm/leads/${lead.id}/activities`),
    serverApiFetch<Page<Task>>(`/api/v1/crm/tasks?lead_id=${lead.id}&status=all&page_size=100`),
    serverApiFetch<Appointment[]>("/api/v1/crm/appointments"),
    lead.can_assign && lead.agency_id
      ? serverApiFetch<{ user_id: string; full_name: string }[]>(
          `/api/v1/agencies/${lead.agency_id}/members`,
        ).catch(() => [])
      : Promise.resolve([]),
  ]);
  const customer = lead.customer;
  const describe = (a: Activity): string => {
    if (a.kind === "STATUS_CHANGE" && a.data) {
      const from = statusName(statuses, String(a.data.from ?? ""), locale);
      const to = statusName(statuses, String(a.data.to ?? ""), locale);
      return locale === "ar" ? `${from} ← ${to}` : `${from} → ${to}`;
    }
    return a.body ?? "";
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/dashboard/crm" className="text-sm text-accent">
            {c.dashboard}
          </Link>
          <h1 className="display-md text-ink">{customer.full_name}</h1>
          <p className="text-sm text-sand-500">
            {statusName(statuses, lead.status_code, locale)} · {c.sources[lead.source]} ·{" "}
            {formatDateTime(lead.created_at, locale)}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="flex flex-col gap-6">
          <Card title={c.pipeline}>
            <LeadEditor
              dict={dict}
              locale={locale}
              lead={lead}
              statuses={statuses}
              members={members}
            />
          </Card>

          <Card title={c.timeline}>
            {lead.can_manage && <ActivityForm dict={dict} leadId={lead.id} />}
            <ol className="mt-4 flex flex-col gap-3">
              {activities.map((a) => (
                <li key={a.id} className="border-s-2 border-brand-200 ps-3">
                  <p className="text-xs text-sand-500">
                    {c.activityKinds[a.kind]} · {formatDateTime(a.occurred_at, locale)}
                    {a.actor && ` · ${a.actor.full_name}`}
                  </p>
                  {describe(a) && (
                    <p className="whitespace-pre-line text-sm text-sand-900">{describe(a)}</p>
                  )}
                </li>
              ))}
            </ol>
          </Card>
        </div>

        <aside className="flex flex-col gap-4">
          <Card title={c.customer}>
            <p className="font-semibold">{customer.full_name}</p>
            {customer.is_platform_user && <p className="text-xs text-success">{c.platformUser}</p>}
            <div className="mt-3 flex flex-col gap-2 text-sm">
              {customer.phone && (
                <>
                  <a href={`tel:${customer.phone}`} dir="ltr" className="text-accent">
                    {c.call}: {customer.phone}
                  </a>
                  <a
                    href={`https://wa.me/${customer.phone.replace(/\D/g, "")}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-success"
                  >
                    {c.whatsapp}
                  </a>
                </>
              )}
              {customer.email && (
                <a href={`mailto:${customer.email}`} dir="ltr" className="text-accent">
                  {customer.email}
                </a>
              )}
              {customer.notes && <p className="text-sand-700">{customer.notes}</p>}
            </div>
            {lead.can_manage && (
              <div className="mt-3">
                <ReplyDraft dict={dict} leadId={lead.id} />
              </div>
            )}
            {(lead.budget_min || lead.budget_max) && lead.budget_currency && (
              <p className="mt-3 text-sm tabular">
                {c.budget}: {formatPrice(lead.budget_min, lead.budget_currency, locale) ?? "…"} –{" "}
                {formatPrice(lead.budget_max, lead.budget_currency, locale) ?? "…"}
              </p>
            )}
          </Card>

          {lead.property && (
            <Card title={c.property}>
              <Link
                href={`/properties/${lead.property.id}`}
                className="font-medium text-accent hover:underline"
              >
                {locale === "en" && lead.property.title_en
                  ? lead.property.title_en
                  : lead.property.title_ar}
              </Link>
              <p className="font-mono text-xs text-sand-500" dir="ltr">
                {lead.property.reference_code}
              </p>
            </Card>
          )}

          <Card title={c.tasks}>
            <TaskPanel
              dict={dict}
              locale={locale}
              leadId={lead.id}
              tasks={tasks.items}
              canManage={lead.can_manage}
            />
          </Card>

          <Card title={c.appointments}>
            <AppointmentPanel
              dict={dict}
              locale={locale}
              leadId={lead.id}
              appointments={appointments.filter((a) => a.lead_id === lead.id)}
              canManage={lead.can_manage}
            />
          </Card>
        </aside>
      </div>
    </div>
  );
}
