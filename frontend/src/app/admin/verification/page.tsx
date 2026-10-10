import Link from "next/link";

import { ActionButton } from "@/features/admin/ActionButton";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

const KINDS = ["IDENTITY", "DOCUMENT", "OWNERSHIP", "LOCATION", "PHONE", "SITE_VISIT"] as const;

interface Queue {
  listings: {
    property_id: string;
    reference_code: string;
    title_ar: string;
    quality_score: number;
  }[];
  agencies: { id: string; name_ar: string; created_at: string }[];
}

export default async function VerificationPage() {
  const me = await requirePermission("properties.verify");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const queue = await serverApiFetch<Queue>("/api/v1/admin/verification/queue");

  return (
    <div className="flex flex-col gap-6">
      <h1 className="display-md text-ink">{a.verification}</h1>
      {me.permissions.includes("agencies.verify") && (
        <section className="flex flex-col gap-2">
          <h2 className="font-semibold">{dict.agency.title}</h2>
          {queue.agencies.length === 0 && <p className="text-sm text-sand-500">{a.emptyQueue}</p>}
          {queue.agencies.map((ag) => (
            <div
              key={ag.id}
              className="flex flex-wrap items-center justify-between gap-2 surface-1 rounded-2xl p-3 text-sm"
            >
              <span>{ag.name_ar}</span>
              <span className="flex gap-2">
                <ActionButton
                  dict={dict}
                  label={a.verifyAgency}
                  path={`/api/v1/agencies/${ag.id}/decision`}
                  body={{ decision: "VERIFY" }}
                  tone="good"
                />
                <ActionButton
                  dict={dict}
                  label={a.rejectAgency}
                  path={`/api/v1/agencies/${ag.id}/decision`}
                  body={{ decision: "REJECT", reason: "{text}" }}
                  prompt={a.reasonPrompt}
                  tone="bad"
                />
              </span>
            </div>
          ))}
        </section>
      )}
      <section className="flex flex-col gap-2">
        <h2 className="font-semibold">{dict.myListings.title}</h2>
        {queue.listings.length === 0 && <p className="text-sm text-sand-500">{a.emptyQueue}</p>}
        {queue.listings.map((item) => (
          <div
            key={item.property_id}
            className="flex flex-col gap-2 surface-1 rounded-2xl p-3 text-sm"
          >
            <Link
              href={`/properties/${item.property_id}`}
              className="font-medium text-accent hover:underline"
            >
              {item.reference_code} · {item.title_ar}
            </Link>
            <div className="flex flex-wrap gap-2">
              {KINDS.map((kind) => (
                <ActionButton
                  key={kind}
                  dict={dict}
                  label={`${a.addVerification}: ${a.verificationKinds[kind]}`}
                  path={`/api/v1/properties/${item.property_id}/verifications`}
                  body={{ kind, result: "PASSED", note: "{text}" }}
                  prompt={a.notePrompt}
                />
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
