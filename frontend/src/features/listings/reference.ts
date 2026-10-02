import "server-only";

import { serverApiFetch } from "@/lib/api/server";
import type { ListingReference } from "@/features/listings/ListingForm";
import type { Place, ReferenceItem } from "@/types/property";

export async function loadListingReference(): Promise<ListingReference> {
  const [types, amenities, governorates] = await Promise.all([
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/amenities"),
    serverApiFetch<Place[]>("/api/v1/locations/governorates"),
  ]);
  return { types, amenities, governorates };
}
