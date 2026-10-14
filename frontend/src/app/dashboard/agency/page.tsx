import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { AgencyTeam, CreateAgencyForm, PendingInvitations } from "@/features/agency/AgencyPanels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import type { Agency, AgencyInvitation, AgencyMember } from "@/types/property";

export const dynamic = "force-dynamic";

export default async function AgencyPage() {
  const me = await requireUser();
  const dict = getDictionary(await getRequestLocale());
  const [agency, invitations] = await Promise.all([
    serverApiFetch<Agency | null>("/api/v1/me/agency"),
    serverApiFetch<AgencyInvitation[]>("/api/v1/me/agency-invitations"),
  ]);
  const members = agency
    ? await serverApiFetch<AgencyMember[]>(`/api/v1/agencies/${agency.id}/members`)
    : [];
  const isOwner = members.some((m) => m.user_id === me.user.id && m.role === "OWNER");
  const a = dict.agency;

  return (
    <div className="page flex flex-col gap-6 pb-8">
      <PageHeader title={a.title} />
      <PendingInvitations dict={dict} invitations={invitations} />
      {agency ? (
        <>
          <Card
            title={agency.name_ar}
            description={agency.name_en ?? undefined}
            actions={
              <StatusBadge tone={agency.status === "VERIFIED" ? "success" : "warning"}>
                {a.statuses[agency.status]}
              </StatusBadge>
            }
          >
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              {agency.phone && (
                <div>
                  <dt className="text-sand-500">{a.phone}</dt>
                  <dd dir="ltr" className="text-start">
                    {agency.phone}
                  </dd>
                </div>
              )}
              {agency.address && (
                <div>
                  <dt className="text-sand-500">{a.address}</dt>
                  <dd>{agency.address}</dd>
                </div>
              )}
            </dl>
          </Card>
          <AgencyTeam dict={dict} agency={agency} members={members} isOwner={isOwner} />
        </>
      ) : (
        <CreateAgencyForm dict={dict} />
      )}
    </div>
  );
}
