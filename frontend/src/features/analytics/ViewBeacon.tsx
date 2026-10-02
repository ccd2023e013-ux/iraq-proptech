"use client";

import { useEffect } from "react";

import { apiFetch } from "@/lib/api/client";

/** Counts one listing view (unique per visitor per day, server-side). Fire-and-forget. */
export function ViewBeacon({ propertyId }: { propertyId: string }) {
  useEffect(() => {
    apiFetch(`/api/v1/analytics/property-views/${propertyId}`, { method: "POST" }).catch(
      () => undefined,
    );
  }, [propertyId]);
  return null;
}
