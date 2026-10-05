import "server-only";

import { serverApiFetch } from "@/lib/api/server";

/**
 * Whether the site can send email (verification and password reset). When
 * the API cannot be reached we assume it can't, so the UI never promises an
 * email that will not arrive.
 */
export async function emailDeliveryAvailable(): Promise<boolean> {
  try {
    const caps = await serverApiFetch<{ email_delivery: boolean }>("/api/v1/auth/capabilities");
    return caps.email_delivery === true;
  } catch {
    return false;
  }
}
