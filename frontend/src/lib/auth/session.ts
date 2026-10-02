import "server-only";

import { cache } from "react";

import { ApiError } from "@/lib/api/client";
import { serverApiFetch } from "@/lib/api/server";
import type { Me } from "@/types/auth";

/**
 * The signed-in user for this request, or null. Cached per request so the
 * header and the page share one /auth/me call.
 */
export const getCurrentUser = cache(async (): Promise<Me | null> => {
  try {
    return await serverApiFetch<Me>("/api/v1/auth/me");
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
    if (error instanceof ApiError && error.code === "NETWORK_ERROR") return null;
    throw error;
  }
});
