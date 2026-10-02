import "server-only";

import { ApiError, apiRequest, parseApiError } from "@/lib/api/client";
import type { Readiness } from "@/types/system";

import type { SystemStatusResult } from "./SystemStatusPanel";

/**
 * Readiness answers 200 when healthy and 503 *with the same body* when a
 * required dependency is down, so both are valid results to display.
 */
export async function loadSystemStatus(): Promise<SystemStatusResult> {
  try {
    const response = await apiRequest("/api/v1/health/ready", { cache: "no-store" });
    if (response.ok || response.status === 503) {
      return { kind: "ok", readiness: (await response.json()) as Readiness };
    }
    const error = await parseApiError(response);
    return { kind: "error", code: error.code };
  } catch (error) {
    return { kind: "error", code: error instanceof ApiError ? error.code : "UNKNOWN" };
  }
}
