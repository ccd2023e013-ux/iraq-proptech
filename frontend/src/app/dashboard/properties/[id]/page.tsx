import { notFound } from "next/navigation";

import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { ListingActions } from "@/features/listings/ListingActions";
import { ListingForm } from "@/features/listings/ListingForm";
import { DocumentManager, MediaManager } from "@/features/listings/MediaManager";
import { loadListingReference } from "@/features/listings/reference";
import { StatusPill } from "@/features/listings/StatusPill";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import { requireUser } from "@/lib/auth/guard";
import { resolveMapConfig } from "@/lib/map/provider";
import type { Property, PropertyDocument } from "@/types/property";

export const dynamic = "force-dynamic";

export default async function EditListingPage({ params }: { params: Promise<{ id: string }> }) {
  await requireUser();
  const { id } = await params;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);

  let property: Property;
  try {
    property = await serverApiFetch<Property>(`/api/v1/properties/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    throw error;
  }
  if (!property.can_edit) notFound();

  const [reference, documents] = await Promise.all([
    loadListingReference(),
    serverApiFetch<PropertyDocument[]>(`/api/v1/properties/${property.id}/documents`),
  ]);
  const f = dict.listingForm;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-brand-900">{f.editTitle}</h1>
          <p className="font-mono text-xs text-sand-500" dir="ltr">
            {property.reference_code}
          </p>
        </div>
        <StatusPill status={property.status} dict={dict} />
      </div>

      {property.status_reason && (
        <Alert tone={property.status === "REJECTED" ? "error" : "warning"}>
          {property.status_reason_code && (
            <strong className="me-1">
              {dict.admin.reasonCodes[
                property.status_reason_code as keyof typeof dict.admin.reasonCodes
              ] ?? property.status_reason_code}
              :
            </strong>
          )}
          {property.status_reason}
        </Alert>
      )}

      <Card title={f.actions}>
        <ListingActions dict={dict} property={property} />
      </Card>
      <Card title={f.media}>
        <MediaManager dict={dict} property={property} />
      </Card>
      <ListingForm
        dict={dict}
        locale={locale}
        reference={reference}
        mapConfig={resolveMapConfig(process.env)}
        initial={property}
      />
      <Card title={f.documents}>
        <DocumentManager dict={dict} propertyId={property.id} documents={documents} />
      </Card>
    </div>
  );
}
