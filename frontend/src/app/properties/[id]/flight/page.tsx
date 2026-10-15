import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { Flight } from "@/features/studio/Flight";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { placeName } from "@/lib/format";
import { resolveMapConfig } from "@/lib/map/provider";
import type { Property } from "@/types/property";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.flight.title, robots: { index: false } };
}

const UUID = /^[0-9a-f-]{36}$/i;

/** Drone flight and construction sequence for one listing (public, read-only). */
export default async function FlightPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const f = dict.flight;
  const property = UUID.test(id)
    ? await serverApiFetch<Property>(`/api/v1/properties/${id}`).catch(() => null)
    : null;
  if (!property) notFound();

  const title = locale === "en" && property.title_en ? property.title_en : property.title_ar;
  const where = [placeName(property.district, locale), placeName(property.city, locale)]
    .filter(Boolean)
    .join("، ");
  const location = property.location_privacy !== "HIDDEN" ? property.display_location : null;
  const floors =
    property.floors ?? (["APARTMENT", "BUILDING"].includes(property.property_type_code) ? 5 : 2);
  const area = Number(property.land_area_m2 ?? property.area_m2 ?? 250) || 250;

  return (
    <div className="page flex flex-col gap-8 pb-10">
      <PageHeader
        title={f.title}
        lede={f.lede}
        context={
          <span className="flex flex-wrap items-center gap-2">
            <Link href={`/properties/${property.id}`} className="hover:text-ink">
              {title}
            </Link>
            <span>· {where}</span>
            {property.is_demo && <TrustBadge kind="demo">{dict.listing.demo}</TrustBadge>}
          </span>
        }
        actions={
          <Link href={`/properties/${property.id}`} className="btn btn-secondary">
            <Icon name="back" className="size-4" />
            {dict.map.openListing}
          </Link>
        }
      />
      {location ? (
        <Flight
          config={resolveMapConfig(process.env)}
          dict={dict}
          locale={locale}
          lon={location.lon}
          lat={location.lat}
          floors={floors}
          areaM2={area}
        />
      ) : (
        <p className="text-ink-2">{f.noLocation}</p>
      )}
    </div>
  );
}
